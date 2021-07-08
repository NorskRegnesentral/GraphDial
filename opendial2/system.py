import time, re, sys, os, tempfile, subprocess, threading, queue, json
from typing import Optional, Dict, Any, List, Set
from . import domain, utils
import zmq
import ast
import mgclient

class DialogueSystem:

    def __init__(self, domain_file: Optional[str]=None):
        self.config = domain.DomainConfig(domain_file)
        self.query_queue: queue.Queue[UpdateRequest]= queue.Queue()
        self.modules = [RuleBasedManager(self.query_queue, self.config),
                        ZeroMQListener(self.query_queue, self.config),
                        ZeroMQSender(self.query_queue, self.config)]
        
        for module in self.modules:
            print("starting", module)
            module.start()

        self.conn = mgclient.connect(host=self.config.params["db_host"], 
                                     port=self.config.params["db_port"])
            
        init_state_request = UpdateRequest("init_state", self.config.initial_state)
        self.query_queue.put(init_state_request)
        self.run()
        

    def run(self):
        
        cursor = self.conn.cursor()
    
        while True:
            print("waiting...")
            request: UpdateRequest = self.query_queue.get()
            print("Processing %i queries from %s"%(len(request.queries), request.origin))
            for query in request.queries:
                print("Query to process:", query)
                expanded_query = utils.get_expansion(query)
                cursor.execute(expanded_query)
            
            self.conn.commit()    
            
            update = UpdateEvent()
            cursor.execute("MATCH (n:New) REMOVE n:New RETURN id(n), labels(n), properties(n);")
            for node_id, labels, properties in cursor.fetchall():
                labels = {l for l in labels if l!="New"}
                update.add_new_node(node_id, labels, properties)
            
            if not update.is_empty():
                print("==> Update:", update)
                for module in self.modules:
                    module.input_queue.put(update)
            self.conn.commit()    
                   

class UpdateEvent:
    
    def __init__(self):
        self.from_id_to_labels: Dict[int,Set[str]] = {}
        self.from_id_to_properties:Dict[int,Dict[str,Any]] = {}
    
    def add_new_node(self, node_id: int, node_labels: Set[str], node_props: Dict[str, Any]):
        self.from_id_to_labels[node_id] = node_labels
        self.from_id_to_properties[node_id] = node_props
        
    def is_empty(self) -> bool:
        return len(self.from_id_to_labels) == 0
    
    def get_new_labels(self) -> Set[str]:
        return {l for labels in self.from_id_to_labels.values() for l in labels}
    
    def get_new_node_ids(self) -> Set[int]:
        return set(self.from_id_to_labels.keys())
    
    def __str__(self) -> str:
        new_nodes_str = []
        for node_id, node_labels in self.from_id_to_labels.items():
            properties_str = str(self.from_id_to_properties[node_id])
            new_node_str = "(n%i:%s %s)"%(node_id, ":".join(node_labels), properties_str)
            new_nodes_str.append(new_node_str)
        return ", ".join(new_nodes_str)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    
class UpdateRequest:
    
    def __init__(self, origin:str, queries:Optional[List[str]]=None):
        self.origin = origin
        self.queries = queries if queries is not None else []
    
    def add_query(self, query: str):
        self.queries.append(query)    
    
    

class AbstractModule(threading.Thread):
    
    def __init__(self, output_queue: queue.Queue, config: domain.DomainConfig):
        super(AbstractModule, self).__init__()
        self.config = config
        self.input_queue: queue.Queue[UpdateEvent] = queue.Queue()
        self.output_queue: queue.Queue[List[str]] = output_queue
        
    def run(self):
        raise NotImplementedError("Must implement the run method of the module")
        # Here we should typically read updates in the input queue, and output
        # the resulting Cypher queries in the output queue
        
    
        
class RuleBasedManager(AbstractModule):
    
    def run(self):
        while True:
            update = self.input_queue.get()
            relevant_rules = self._get_relevant_rules(update.get_new_labels())
            new_nodes = update.get_new_node_ids()
            if relevant_rules:
                request = UpdateRequest("rules")
                for r in relevant_rules:
                    request.add_query(utils.focus_on_nodes(r, new_nodes))
                self.output_queue.put(request)
                    

    def _get_relevant_rules(self, new_labels:Set[str]):

        relevant_rules = []
        for rule in self.config.update_rules:

            change_op_match = re.search("(?:CREATE|MERGE|SET|DELETE|REMOVE|DETACH)", rule)
            if not change_op_match:
                raise RuntimeError("Rule does not contain any state change operation: %s"%rule)
            condition_part = rule[:change_op_match.start()]
            for label in new_labels:
                if re.search("\:%s[\s\:]"%re.escape(label), condition_part):
                    relevant_rules.append(rule)
                    break

        return relevant_rules
    
            

class ZeroMQListener(AbstractModule):
    
    def run(self):
        context = zmq.Context() # type: ignore
        socket = context.socket(zmq.PULL) # type: ignore
        socket.bind("tcp://*:%i"%self.config.params["zmq_input_port"])
        while True:
            message = socket.recv_json()

            if message["label"]=="HumanUtterance":
                converter = convert_asr_results
            else:
                converter = default_converter

            request = UpdateRequest("listener", converter(message))
            self.output_queue.put(request)
             

class ZeroMQSender(AbstractModule):
    
    def run(self):
        context = zmq.Context() # type: ignore
        socket = context.socket(zmq.PUSH) # type: ignore
        socket.bind("tcp://*:%i"%(self.config.params["zmq_output_port"]))

        while True:
            update = self.input_queue.get()
            for node_id, node_labels in update.from_id_to_labels.items():
                if any(l for l in node_labels if l in self.config.outputs):
                    props = update.from_id_to_properties[node_id]
                    socket.send_json(props)


def convert_asr_results(mess_dict: Dict[str,Any]) -> List[str]:
          
    queries = [ f"MERGE (u:HumanUtterance {{id:{mess_dict['id']}}}) "
               + f"SET u.start={mess_dict['start']}, u.end={mess_dict['end']};",
               
               f"MATCH (u:HumanUtterance {{id:{mess_dict['id']}}})-[:alternative]->(r_old:ASRHypothesis) "
               + "DETACH DELETE r_old ;"]
    
    for hypo in mess_dict["hypotheses"]:#ast.literal_eval(mess_dict["hypotheses"]):
        if (not mess_dict["isFinal"]): hypo["confidence"] = 0.7
        if (mess_dict["isFinal"]): mess_dict["stability"] = 0.7
        properties = f"{{transcript:\"{hypo['transcript']}\", prob:{hypo['confidence']}, stability:{mess_dict['stability']}}}"

        queries.append(f"MATCH (u:HumanUtterance {{id:{mess_dict['id']}}}) "
                       + f"CREATE (r_new:ASRHypothesis {properties})<-[:alternative]-(u) ;")

    floor_status = "free" if mess_dict.get("isFinal", False) else "busy"
    queries.append(f"MERGE (f:Floor) SET f.status='{floor_status}';")

    queries = [utils.normalise_query(q) for q in queries]
    return queries



def default_converter(mess_dict: Dict[str,Any]) -> List[str]:

    props = (", ".join("%s:%s"%(k, '%s'%v if type(v)==str else str(v))
                       for k, v in mess_dict.items() if k != "label"))
    cypher_query = "CREATE {n:%%s {%s} ;"%(mess_dict["type"], props)
    return [cypher_query]