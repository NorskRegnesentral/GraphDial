import re, queue, json, threading, time
from typing import Any, Dict, List, Optional, Set, Tuple
import mgclient
from . import utils, domain

NODE_REGEX = "\\((\\w+?)\\:(\\w+?)( .+?)?\\)"

class DialogueManager:

    def __init__(self, config : domain.DomainConfig):

        self.config = config
        self.conn = mgclient.connect(host=config.params["db_host"], port=config.params["db_port"])

        self.input_queue: queue.Queue[List[str]] = queue.Queue()
        self.output_queue: queue.Queue[Dict[str,Any]] = queue.Queue()

        self.input_queue.put(config.initial_state)


    def run(self):
        new_nodes = []
        while True:
            queries_to_run = self.input_queue.get()
            cursor = self.conn.cursor()
            for query in queries_to_run:
                print("Initial query to process:", query)
                expanded_query = get_expansion(query)
                print("Running expansion:", expanded_query, "\n---")
                cursor.execute(expanded_query)

            if new_nodes:
                clear_query = "MATCH (n) WHERE id(n) IN %s REMOVE n:New;"%str(new_nodes)
                cursor.execute(clear_query)
                self.conn.commit()

            new_nodes.clear()
            new_labels = set()
            cursor.execute("MATCH (n:New) RETURN id(n), labels(n), properties(n);")
            for node_id, labels, properties in cursor.fetchall():
                new_nodes.append(node_id)
                new_labels.update(labels)
                properties = {"labels":labels, **properties}
                self.output_queue.put(properties)
            print("==> New nodes:", new_nodes, "with labels:", new_labels)

            next_rules = self._get_relevant_next_rules(new_labels)
            if next_rules:
                self.input_queue.put(next_rules)
            else:
                clear_query = "MATCH (n) WHERE id(n) IN %s REMOVE n:New;"%str(new_nodes)
                cursor.execute(clear_query)


    def _get_relevant_next_rules(self, new_labels:Set[str]):

        relevant_rules = []
        for rule in self.config.update_rules:

            change_op_match = re.search("(?:CREATE|MERGE|SET|DELETE|REMOVE|DETACH)", rule)
            if not change_op_match:
                raise RuntimeError("Rule does not contain any state change operation: %s"%rule)
            condition_part = rule[:change_op_match.start()]
            for label in new_labels:
                if ":%s"%label in condition_part:
                    relevant_rules.append(rule)
                    break

        return relevant_rules


def get_expansion(init_query:str):

    init_query = utils.normalise_query(init_query)

    change_op_match = re.search("(?:CREATE|MERGE|SET|DELETE|REMOVE|DETACH)", init_query)
    if not change_op_match:
        raise RuntimeError("Rule does not contain any state change operation: %s"%init_query)

    condition_part = init_query[:change_op_match.start()]
    effect_part = init_query[change_op_match.start():]

    if len(condition_part) and ":" in condition_part:
        condition_part = condition_part.replace(":", ":New:", 1)

    assignments = []
    for effect_node in re.finditer(NODE_REGEX, effect_part):
        anchor = effect_node.group(1)

        assignments.append("%s:New"%anchor)
        assignments.append("%s.created=CASE WHEN %s.created IS NULL THEN timestamp()"%(anchor, anchor)
                           + " ELSE %s.created END"%(anchor))
        assignments.append("%s.last_updated=timestamp()"%anchor)

        if assignments:
            effect_part = effect_part.strip(";") + " SET " + ", ".join(assignments) + ";"

    return condition_part + effect_part
