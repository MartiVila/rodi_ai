# Enviroment/TrafficManager.py

class TrafficManager:
    """
    Control Centralitzat (CTC).
    BIDIRECTIONAL LOGIC:
    Manages tracks as shared resources. Track 0 (A->B) is the same as Track 0 (B->A).
    """
    _reported_obstacles = {}
    _train_positions = {}

    @staticmethod
    def _get_key(u_id, v_id, track_id):
        """Returns a unique key for the physical track, regardless of direction."""
        ids = sorted([str(u_id), str(v_id)])
        return f"{ids[0]}-{ids[1]}-{track_id}"

    @staticmethod
    def report_issue(u_id, v_id, track_id):
        key = TrafficManager._get_key(u_id, v_id, track_id)
        TrafficManager._reported_obstacles[key] = "ALERT"

    @staticmethod
    def clear_issue(u_id, v_id, track_id):
        key = TrafficManager._get_key(u_id, v_id, track_id)
        if key in TrafficManager._reported_obstacles:
            del TrafficManager._reported_obstacles[key]

    @staticmethod
    def check_alert(u_id, v_id, track_id):
        key = TrafficManager._get_key(u_id, v_id, track_id)
        return 1 if key in TrafficManager._reported_obstacles else 0

    @staticmethod
    def reset():
        TrafficManager._reported_obstacles.clear()
        TrafficManager._train_positions.clear()

    @staticmethod
    def update_train_position(edge, train_id, progress):
        key = TrafficManager._get_key(edge.node1.id, edge.node2.id, edge.track_id)
        
        if key not in TrafficManager._train_positions:
            TrafficManager._train_positions[key] = []
        
        TrafficManager._train_positions[key] = [
            entry for entry in TrafficManager._train_positions[key] if entry['id'] != train_id
        ]
        
        TrafficManager._train_positions[key].append({
            'id': train_id,
            'u': edge.node1.id,
            'v': edge.node2.id,
            'progress': progress
        })

    @staticmethod
    def get_occupants(edge):
        key = TrafficManager._get_key(edge.node1.id, edge.node2.id, edge.track_id)
        entries = TrafficManager._train_positions.get(key, [])
        return [e['id'] for e in entries]

    @staticmethod
    def get_nearest_train_ahead(edge, my_progress, my_id):
        key = TrafficManager._get_key(edge.node1.id, edge.node2.id, edge.track_id)
        entries = TrafficManager._train_positions.get(key, [])
        
        min_dist = None
        my_u = edge.node1.id
        
        for entry in entries:
            if entry['id'] == my_id: continue
            
            other_u = entry['u']
            other_p = entry['progress']
            
            dist = None
            
            if other_u == my_u:
                if other_p > my_progress:
                    dist = other_p - my_progress
            else:
                rel_pos = 1.0 - other_p
                if rel_pos > my_progress:
                    dist = rel_pos - my_progress
            
            if dist is not None:
                if min_dist is None or dist < min_dist:
                    min_dist = dist
                    
        return min_dist

    @staticmethod
    def remove_train(train_id):
        for key in TrafficManager._train_positions:
            TrafficManager._train_positions[key] = [
                e for e in TrafficManager._train_positions[key] if e['id'] != train_id
            ]