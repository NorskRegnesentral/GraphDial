import time, re, sys, os, tempfile, subprocess
from typing import Optional, Dict, Any, List, Union
import yaml
import mgclient
                

class DialogueSystem:
    
    def __init__(self, domain_file: Optional[str]=None):
        self.config = DomainConfig(domain_file)
        self.conn = DBConnection(self.config.params["host"], self.config.params["port"])
    
class DomainConfig:
    
    def __init__(self, filename:Optional[str]=None):
        
        self.params: Dict[str, Any] = {"host":"localhost", "port":7687}  
        self.modules: Dict[str, str] = {}
        self.initial_state: List[str] = []
        self.state_update_rules: List[str] = []
        
        if filename is None:
            print("No configuration file provided, starting new blank configuration file")
            new_file, filename = tempfile.mkstemp()
            os.write(new_file, b"modules:\ninitial_state:\nstate_update_rules:\n")
            os.close(new_file)
            
        self.filename = filename
        self.read_from_file(filename)
            
            
    def read_from_file(self, filename: str):
        
        filename = os.path.expanduser(filename)
        if not os.path.exists(filename):
            raise RuntimeError("Domain file '%s' does not exist"%filename)
        
        with open(filename, "r") as fd:
            dico = yaml.load(fd.read())
            
            if dico.get("modules", None) is not None:
                if type(dico["modules"])!= str:
                    raise RuntimeError("Modules must be a dictionary")
                for module_name, module_path in dico["modules"]:
                    if not os.path.exists(module_path):
                        raise RuntimeError(module_path + " does not exist")
                    self.modules[module_name] = module_path
                
            if dico.get("initial_state", None) is not None:
                if type(dico["initial_state"])==str:
                    self.initial_state = dico["initial_state"].split("\n")
                elif type(dico["initial_state"])==list:
                    self.initial_state = dico["initial_state"]
                else:
                    raise RuntimeError("The initial state should be a list of Cypher queries")
                
                for i, l in enumerate(self.initial_state):
                    if not l.upper().startswith("CREATE"):
                        print("WARNING: initial state query is not CREATE operation:", l)
                    if not l.strip().endswith(";"):
                        self.initial_state[i] = l + ";"
                        
            if dico.get("state_update_rules", None) is not None:
                if type(dico["state_update_rules"])==str:
                    self.state_update_rules = dico["state_update_rules"].split("\n")
                elif type(dico["state_update_rules"])==list:
                    self.state_update_rules = dico["state_update_rules"]
                else:
                    raise RuntimeError("State update rules should be a list of Cypher queries")
                
                for i, l in enumerate(self.state_update_rules):
                    if not l.strip().endswith(";"):
                        self.state_update_rules[i] = l + ";"
                        
            else:
                print("WARNING: You have not provided any single state update rules, are you sure this is correct?")
                
            for param in dico:
                if param not in {"initial_state", "state_update_rules"}:
                    self.params[param] = dico[param]
                    
                    
class DBConnection:
    
    def __init__(self, host: str, port: int):
        
        if host=="localhost":
            
            docker_images = subprocess.run("docker ps", shell=True, capture_output=True)
            if len(docker_images.stderr) > 0:
                raise RuntimeError(docker_images.stderr.decode("utf-8"))
            elif "memgraph" in str(docker_images.stdout):
                print("memgraph already running, stopping it")
                subprocess.run('docker stop $(docker ps -q --filter ancestor=memgraph)', shell=True)
            
            p = subprocess.Popen("docker run -h %s -p %i:%i  -v mg_lib:/var/lib/memgraph   -v mg_log:/var/log/memgraph   -v mg_etc:/etc/memgraph  memgraph"%(host, port, port),
                                 shell=True, stdout=subprocess.PIPE)
            for line in iter(p.stdout.readline, ''):
                print(line.decode("utf-8"))
                break
                
        conn = mgclient.connect(host=host, port=port)        
                    
        