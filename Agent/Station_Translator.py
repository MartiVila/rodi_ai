class StationTranslator:
    """
        S'encarregara de Passar les dades de Enviroment a Dades que l'Agent pugui interpretar
    """

    """
    Converts environment information (trains, nodes, etc.) to a discrete state id.

    This is the only place that knows about the real structure
    of the railway network. The agent only sees integer states.
    """

    def __init__(self, n_trains: int, n_nodes: int):
        self.n_trains = n_trains
        self.n_nodes = n_nodes
        # total number of discrete states
        self.n_states = n_trains * n_nodes

    def encode(self, train_id: int, node_id: int) -> int:
        """
        Map (train_id, node_id) -> state index in [0, n_states-1].
        Adapt this as your environment becomes more complex
        (e.g., include delay, direction, etc.).
        """
        return train_id * self.n_nodes + node_id

    def decode(self, state: int) -> tuple[int, int]:
        """
        Map state index -> (train_id, node_id).
        """
        train_id = state // self.n_nodes
        node_id = state % self.n_nodes
        return train_id, node_id
