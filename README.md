# GraphDial

GraphDial is a versatile software framework to develop (text or speech-based) dialogue systems, with a particular focus on dialogue management. The framework is fully domain-independent and can be employed to construct dialogue systems for various domains. External modules can be easily plugged in and out of the framework to provide additional functions related to speech recognition, natural language understanding, speech synthesis, situational awareness, etc. 

GraphDial relies on *graphs* to represent the dialogue state. Dialogue state tracking and action selection are consequently viewed as *graph operations*.  Such graph operations are encoded using the [Cypher](https://docs.memgraph.com/cypher-manual) open graph query language.

---

This repo contains work in progress and currently has only a few example intents working.

`/data/nlu.yml` contains NLU examples/lookup.

To train the NLU model, first install [Rasa](https://rasa.com/docs/rasa/installation). You can then use the `rasa train nlu` command to train a new model which will be saved to the `/models` folder. This only requires that you define the training data in the yml file. See the [Rasa documentation](https://rasa.com/docs/rasa/nlu-training-data) for more information about the NLU training data format.

`/domains/hri_example.yaml` mainly specifies the Cypher query update rules as well as ip addresses for input and output to the dialog manager server.

`/graphdial` contains the source code for the dialog manager. 

`/models` contains a trained Rasa NLU model and stores any new trained models.

`/notebooks` contains three Jupyter notebooks. `step_by_step_graph_updates_code.ipynb` shows the step by step execution of Cypher queries associated with Figure 2 in the paper. `graphdial_test_send.ipynb` and `graphdial_test_receive.ipynb` shows example code on how to send and receive requests from the dialog system. See the notebook for a concrete example of the format of the requests.

---

Before running the dialog system, an instance of Memgraph needs to be running. Follow the instructions on [https://memgraph.com/download](https://memgraph.com/download) to set it up. 

To implement your own query modules, see [https://docs.memgraph.com/memgraph/database-functionalities/query-modules/implement-query-modules/](https://docs.memgraph.com/memgraph/database-functionalities/query-modules/implement-query-modules/) 
