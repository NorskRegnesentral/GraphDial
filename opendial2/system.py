import time, re, sys, os, tempfile, subprocess, threading, queue, json
from typing import Callable, Generator, Optional, Dict, Any, List, Union
from . import manager, domain, utils
import zmq

class DialogueSystem:
    
    def __init__(self, domain_file: Optional[str]=None):
        self.config = domain.DomainConfig(domain_file)
        self.manager = manager.DialogueManager(self.config)
                
        listen_thread = threading.Thread(target=listen_to_inputs, 
                             args=(self.manager.input_queue, self.config))
        sendoff_thread = threading.Thread(target=send_outputs, 
                             args=(self.manager.output_queue, self.config))
        listen_thread.start()
        sendoff_thread.start()        

        self.manager.run()
                  
def listen_to_inputs(input_queue: queue.Queue, 
                     config: domain.DomainConfig):
    context = zmq.Context() # type: ignore
    socket = context.socket(zmq.PULL) # type: ignore
    socket.bind("tcp://*:%i"%config.params["zmq_input_port"])
    while True:
        message = socket.recv_json()
        if message.get("label", None) in config.inputs:
            
            if message["label"]=="HumanUtterance":
                converter = convert_asr_results
            else:
                converter = default_converter
        
            queries = converter(message)
            input_queue.put(queries)
        

def send_outputs(output_queue: queue.Queue, 
                 config: domain.DomainConfig):

    context = zmq.Context() # type: ignore
    socket = context.socket(zmq.PUSH) # type: ignore
    socket.bind("tcp://*:%i"%(config.params["zmq_output_port"]))
   
    while True:
        message = output_queue.get()
        if any(l in config.outputs for l in message.get("labels", [])):        
            socket.send_json(message)

   
def convert_asr_results(mess_dict: Dict[str,Any]) -> List[str]:
          
    queries = [ f"MERGE (u:HumanUtterance {{id:{mess_dict['id']}}}) "
               + f"SET u.start={mess_dict['start']}, u.end={mess_dict['end']};",
               
               f"MATCH (u:HumanUtterance {{id:{mess_dict['id']}}})-[:alternative]->(r_old:ASRHypothesis) "
               + "DETACH DELETE r_old ;"]
    
    for hypo in mess_dict["hypotheses"]:
        properties = f"{{transcript:'{hypo['transcript']}', prob:{hypo['prob']}, stability:{hypo['stability']}}}"
        queries.append(f"MATCH (u:HumanUtterance {{id:{mess_dict['id']}}}) "
                       + f"CREATE (r_new:ASRHypothesis {properties})<-[:alternative]-(u) ;")
    
    floor_status = "free" if mess_dict.get("is_Final", False) else "busy"
    queries.append(f"MERGE (f:Floor) SET f.status='{floor_status}';")
    
    queries = [utils.normalise_query(q) for q in queries]
    return queries
    


def default_converter(mess_dict: Dict[str,Any]) -> List[str]:
    
    props = (", ".join("%s:%s"%(k, '%s'%v if type(v)==str else str(v))
                       for k, v in mess_dict.items() if k != "label"))
    cypher_query = "CREATE {n:%%s {%s} ;"%(mess_dict["type"], props)    
    return [cypher_query]
