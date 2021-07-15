from __future__ import annotations
import time, re, sys, os, tempfile, subprocess
from typing import Optional, Dict, Any, List, Set, Union
import yaml
from . import utils               

NODE_REGEX = "\\((\\w*?)\\:(\\w*?)( .+?)?\\)"
       
class DomainConfig:
    
    def __init__(self, filename:Optional[str]=None):
        
        self.params: Dict[str, Any] = {"db_host":"localhost", "db_port":7687, 
                                       "zmq_input_port":5555, "zmq_output_port":5556}  
        self.modules: Dict[str, str] = {}
        
        self.initial_state: List[str] = []
        self.update_rules: List[str] = []
        
        if filename is None:
            print("No configuration file provided, starting new blank configuration file")
            new_file, filename = tempfile.mkstemp()
            os.write(new_file, b"modules:\ninitial_state:\nupdate_rules:\n")
            os.close(new_file)
            
        self.filename = filename
        self.read_from_file(filename)
            
            
    def read_from_file(self, filename: str):
        
        filename = os.path.expanduser(filename)
        if not os.path.exists(filename):
            raise RuntimeError("Domain file '%s' does not exist"%filename)
        
        with open(filename, "r") as fd:
            dico = yaml.safe_load(fd.read())
            
            if "inputs" not in dico:
                raise RuntimeError("Must specify the types of inputs the " +
                                   "dialogue manager should listen to")
            self.inputs = dico["inputs"]
            if "outputs" not in dico:
                raise RuntimeError("Must specify the types of output the " +
                                   "dialogue manager should forward")
            self.outputs = dico["outputs"]
            if dico.get("modules", None) is not None:
                if type(dico["modules"])!= str:
                    raise RuntimeError("Modules must be a dictionary")
                for module_name, module_path in dico["modules"]:
                    if not os.path.exists(module_path):
                        raise RuntimeError(module_path + " does not exist")
                    self.modules[module_name] = module_path
                
            if dico.get("initial_state", None) is not None:
                if type(dico["initial_state"])==str:
                    self.initial_state = [q for q in dico["initial_state"].split(";") if len(q) > 2]
                elif type(dico["initial_state"])==list:
                    self.initial_state = dico["initial_state"]
                else:
                    raise RuntimeError("The initial state should be a list of Cypher queries")
                self.initial_state = [utils.normalise_query(rule) for rule in self.initial_state]
                for initial_state_query in self.initial_state:
                    if not re.search("(?:CREATE|MERGE)", initial_state_query):
                        raise RuntimeError("Initial state query does not start with CREATE/MERGE: %s"%initial_state_query)
            self.initial_state.insert(0, "MATCH (n) DETACH DELETE n;")

            if dico.get("update_rules", None) is not None:
                if type(dico["update_rules"])==str:
                    self.update_rules = [q for q in dico["update_rules"].split(";") if len(q) > 2]
                elif type(dico["update_rules"])==list:
                    self.update_rules = dico["update_rules"]
                else:
                    raise RuntimeError("The state update rules should be a list of Cypher queries")
                self.update_rules = [utils.normalise_query(rule) for rule in self.update_rules]
                for update_rule in self.update_rules:
                    if not update_rule.startswith("MATCH"):
                        raise RuntimeError("Rule does not start with a MATCH condition: %s"%update_rule)
                        
            else:
                print("WARNING: You have not provided any single state update rules, are you sure this is correct?")
                
            for param in dico:
                if param not in {"initial_state", "update_rules"}:
                    self.params[param] = dico[param]
                    
                    



      

    