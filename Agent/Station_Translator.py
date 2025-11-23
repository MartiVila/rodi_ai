"""
    S'encarregara de Passar les dades de Enviroment a Dades que l'Agent pugui interpretar
"""

class Station_Translator:
    def __init__(self, n_trains, n_nodes):
        self.n_trains = n_trains
        self.n_nodes = n_nodes

    def encode(self, train_id, node_id):
        # [0..n_trains*n_nodes-1]
        return train_id * self.n_nodes + node_id

    def decode(self, state_index):
        train_id = state_index // self.n_nodes
        node_id = state_index % self.n_nodes
        return train_id, node_id
