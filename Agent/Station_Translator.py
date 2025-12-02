class StationTranslator:
    """
    S'encarregara de Passar les dades de Enviroment a Dades que l'Agent pugui interpretar

    Es a dir, passa les dades del enviroment en un id de situació
    Fa que cada estat sigui un estat discret, amb un id
    

    Potser podriem definir enums o dicts d'encoding
    """



    """
    Començar amb agafar parametres:
        Stat_tren=[estació a la que va,  Estacio de la que ve,  delay]

    ->Problema és que el tren no va en hora, i volem que vagi en hora

    """

    line_station=[]
    delay_translator={"Retard_Nul":0, "Retard_Moderat":1, "Retard_Insalvable":2 }

    def __init__(self, n_trains: int, n_nodes: int):
        self.n_trains = n_trains
        self.n_nodes = n_nodes
        self.line_station=[None for i in range(len(n_nodes))]
        # total number of discrete states
        self.n_states = n_trains * n_nodes


    def encode(self, train_id: int, node_id: int, delay: int) -> int:
        """
        """

        encoded_delay=0
        encoded_pre_station=0
        encoded_post_station=0

        if delay < 15:
            encoded_delay=self.delay_translator["Retard_Nul"]

        elif delay > 30:
            encoded_delay=self.delay_translator["Retard_Insalvable"]

        else:
            encoded_delay=self.delay_translator["Retard_Moderat"]
        


        return encoded_post_station*100+encoded_pre_station*10+encoded_delay

    def decode(self, state: int) -> tuple[int, int]:
        """
        Map state index -> (train_id, node_id).
        """
        train_id = state // self.n_nodes
        node_id = state % self.n_nodes
        return train_id, node_id
