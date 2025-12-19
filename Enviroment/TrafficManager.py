# Enviroment/TrafficManager.py

class TrafficManager:
    """
    Actua com un 'Control Centralitzat' (CTC) o ràdio compartida.
    Els trens reporten aquí si troben problemes, i consulten abans de decidir.
    Pattern: Singleton / Static Static State
    """
    # Diccionari: {(node_origen, node_desti, via_id): "ALERT"}
    _reported_obstacles = {}
    _train_positions = {}

    @staticmethod
    def report_issue(u_id, v_id, track_id):
        """Un tren avisa que aquesta via va lenta."""
        key = (u_id, v_id, track_id)
        TrafficManager._reported_obstacles[key] = "ALERT"

    @staticmethod
    def clear_issue(u_id, v_id, track_id):
        """Un tren avisa que aquesta via està neta."""
        key = (u_id, v_id, track_id)
        if key in TrafficManager._reported_obstacles:
            del TrafficManager._reported_obstacles[key]

    @staticmethod
    def check_alert(u_id, v_id, track_id):
        """Retorna 1 si hi ha alerta, 0 si no."""
        return 1 if (u_id, v_id, track_id) in TrafficManager._reported_obstacles else 0

    @staticmethod
    def reset():
        """Neteja tots els avisos (per quan es reinicia el dia)."""
        TrafficManager._reported_obstacles.clear()
    @staticmethod
    def update_train_position(edge, train_id, progress):
        """Actualitza la posició d'un tren en un tram concret."""
        if edge not in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = []
        
        # Eliminem l'entrada vella d'aquest tren si hi és
        TrafficManager._train_positions[edge] = [
            (tid, prog) for tid, prog in TrafficManager._train_positions[edge] if tid != train_id
        ]
        # Afegim la nova
        TrafficManager._train_positions[edge].append((train_id, progress))
        
        # Ordenem els trens per progrés (del més avançat al més endarrerit)
        TrafficManager._train_positions[edge].sort(key=lambda x: x[1], reverse=True)

    @staticmethod
    def get_nearest_train_ahead(edge, my_progress, my_id):
        """
        Retorna la distància (en % de 0.0 a 1.0) al tren del davant.
        Si no hi ha ningú, retorna None.
        """
        if edge not in TrafficManager._train_positions:
            return None
            
        # Busquem trens en el mateix edge que estiguin per davant meu (progress > my_progress)
        trains_on_edge = TrafficManager._train_positions[edge]
        
        for tid, t_prog in trains_on_edge:
            if tid != my_id and t_prog > my_progress:
                return t_prog - my_progress # Distància relativa (0.1 vol dir 10% del tram)
        
        return None # Via lliure per davant

    @staticmethod
    def remove_train(train_id):
        """Neteja el tren del registre (quan acaba o canvia de via)."""
        for edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]