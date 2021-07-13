# OpenDial 2

OpenDial 2 is a versatile software framework to develop (text or speech-based) dialogue systems, with a particular focus on dialogue management. The framework is fully domain-independent and can be employed to construct dialogue systems for various domains. External modules can be easily plugged in and out of the framework to provide additional functions related to speech recognition, natural language understanding, speech synthesis, situational awareness, etc. 

OpenDial 2 relies on *probabilistic graphs* to represent the dialogue state. Dialogue state tracking and action selection are consequently viewed as *graph operations*.  Such graph operations are encoded using the [Cypher](https://docs.memgraph.com/cypher-manual) open graph query language.

This repo contains work in progress and currently has only a few example intents working.

`/data/nlu.yml` contains NLU examples/lookup.

`/domains/hri_example.yaml` mainly specifies the Cypher query update rules as well as ip addresses for input and output to the dialog manager server.

`/models` contains a Rasa NLU models folder with a trained model.

`/notebooks/step_by_step_graph_updates_code.ipynb` contains a Jupyter notebook showing the step by step execution of Cypher queries associated with Figure 2 in the paper.

`/opendial2` contains the source code for the dialog manager. 

