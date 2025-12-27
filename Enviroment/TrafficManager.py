import pandas as pd
import math
import random
import unicodedata
import re
from collections import defaultdict

# Imports del projecte
from Agent.QlearningAgent import QLearningAgent
from Enviroment.Datas import Datas
from Enviroment.Node import Node
from Enviroment.Edge import Edge
from Enviroment.EdgeType import EdgeType

# Valors per defecte
#DEFAULT_AGENT_PARAMS = [0.7, 0.99, 0.99]
DEFAULT_AGENT_PARAMS = [0.5, 0.99, 0.01]

class TrafficManager:
    """
    Classe central del Model (MVC). Actua com a 'Singleton' de facto.
    """
    
    # === ESTAT COMPARTIT (Shared Memory) ===
    _reported_obstacles = {}       # {(node_u, node_v, track_id): "ALERT"}
    _train_positions = {}          # {Edge: [(train_id, progress), ...]}
    _physical_segments = {}        # {(node_u_name, node_v_name): EdgeObject}
    
    # === CONFIGURACIÓ ===
    SPAWN_INTERVAL = 45    
    RESET_INTERVAL = 210   
    CHAOS_INTERVAL = 60    

    def __init__(self, width=1400, height=900, is_training=False):
        self.is_training = is_training 
        self.width = width
        self.height = height

        self.nodes = {}
        self.all_edges = []
        self.lines = {}
        self.active_trains = []
        self.completed_train_logs = []

        self.sim_time = 0.0
        self.last_spawn = -999 
        self.last_reset = 0
        self.last_chaos = 0
        
        self.current_spawn_line = 'R1_NORD' 

        # === CERVELL (Agent Compartit) ===
        self.brain = QLearningAgent(
            alpha=DEFAULT_AGENT_PARAMS[0], 
            gamma=DEFAULT_AGENT_PARAMS[1], 
            epsilon=DEFAULT_AGENT_PARAMS[2]
        )
        try:
            self.brain.load_table("Agent/Qtables/q_table.pkl")
            if not self.is_training:
                print("[TrafficManager] Cervell (Q-Table) carregat correctament.")
        except Exception:
            print("[TrafficManager] ALERTA: No s'ha trobat taula prèvia. Iniciant des de zero.")

        self._load_network()

    # ############################################################################################
    # Bucle Principal
    # ############################################################################################

    def update(self, dt_minutes):
        self.sim_time += dt_minutes
        self._handle_mechanics()

        # SPAWN
        if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
            self.last_spawn = self.sim_time
            
            if self.is_training:
                line_anada = self.current_spawn_line
                line_tornada = f"{self.current_spawn_line}_SUD"
            else:
                line_anada = 'R1_NORD'
                line_tornada = 'R1_SUD'

            self.spawn_line_train(line_anada)
            if line_tornada in self.lines:
                self.spawn_line_train(line_tornada)

        # UPDATE TRENS
        for t in self.active_trains[:]:
            t.update(dt_minutes)
            
            if t.finished:
                self._archive_train_log(t)
                self.remove_train(t.id) 
                self.active_trains.remove(t)

    def _handle_mechanics(self):
        # Manteniment
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            self.reset_network_status()

        # Caos (Visual)
        if not self.is_training and (self.sim_time - self.last_chaos > self.CHAOS_INTERVAL):
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()

    def reset_network_status(self):
        for e in self.all_edges: 
            e.edge_type = EdgeType.NORMAL
            e.update_properties()
        TrafficManager._reported_obstacles.clear()

    # ############################################################################################
    # Gestió de Trens
    # ############################################################################################

    def spawn_line_train(self, line_name):
        from Enviroment.Train import Train 

        if line_name not in self.lines: return
        
        station_names_raw = self.lines[line_name]
        route_nodes = []
        for name_raw in station_names_raw:
            name_norm = self._normalize_name(name_raw)
            if name_norm in self.nodes:
                route_nodes.append(self.nodes[name_norm])
        
        if len(route_nodes) > 1:
            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            
            new_train = Train(
                agent=self.brain, 
                route_nodes=route_nodes, 
                schedule=schedule, 
                start_time_sim=self.sim_time, 
                is_training=self.is_training
            )
            
            self.active_trains.append(new_train)
            if not self.is_training:
                print(f"[Spawn] Tren {new_train.id} sortint de {route_nodes[0].name}")

    def calculate_schedule(self, route_nodes, start_time):
        schedule = {}
        current_time = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        
        for i in range(len(route_nodes) - 1):
            u_name = route_nodes[i].name
            v_name = route_nodes[i+1].name
            
            edge = self.get_edge(u_name, v_name)
            travel_time = edge.expected_minutes if edge else 3.0
            current_time += travel_time + Datas.STOP_STA_TIME
            schedule[route_nodes[i+1].id] = current_time
            
        return schedule

    def _archive_train_log(self, train):
        log_entry = {
            'id': train.id,
            'schedule': train.schedule.copy(),
            'actuals': train.arrival_logs.copy(),
            'route_map': {n.id: n.name for n in train.route_nodes}
        }
        self.completed_train_logs.append(log_entry)

    # ############################################################################################
    # Càrrega de Dades (CSV)
    # ############################################################################################

    def _load_network(self):
        print("[TrafficManager] Carregant xarxa ferroviària...")
        
        wanted_stations = set()
        for s1, s2 in Datas.R1_CONNECTIONS:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception as e:
            print(f"[Error CRÍTIC] No s'ha pogut llegir {csv_path}: {e}")
            return

        lats, lons, temp_st = [], [], []
        for _, row in df.iterrows():
            name = row.get('NOMBRE_ESTACION')
            norm_name = self._normalize_name(name)
            
            if norm_name not in wanted_stations: continue 

            lat = self._parse_coord(row.get('LATITUD'), True)
            lon = self._parse_coord(row.get('LONGITUD'), False)
            
            if name and lat and lon:
                temp_st.append({
                    'id': str(row.get('ID')), 
                    'norm': norm_name, 
                    'orig': name, 
                    'lat': lat, 'lon': lon
                })
                lats.append(lat)
                lons.append(lon)

        if not lats: 
            print("[Error] No s'han trobat estacions vàlides.")
            return

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        margin = 100

        for st in temp_st:
            # Evitem divisió per zero si només hi ha 1 punt
            den_lon = (max_lon - min_lon) if (max_lon - min_lon) > 0 else 1
            den_lat = (max_lat - min_lat) if (max_lat - min_lat) > 0 else 1

            x = ((st['lon'] - min_lon) / den_lon) * (self.width - margin) + 50
            y = self.height - (((st['lat'] - min_lat) / den_lat) * (self.height - margin) + 50)
            
            node = Node(x, y, st['id'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            self.nodes[st['norm']] = node

        for s1, s2 in Datas.R1_CONNECTIONS: 
            self._add_connection(s1, s2)
            
        self.lines['R1_NORD'] = Datas.R1_STA
        self.lines['R1_SUD'] = Datas.R1_STA[::-1]
        
        print(f"[TrafficManager] Xarxa construïda: {len(self.nodes)} estacions, {len(self.all_edges)} vies.")

    def _add_connection(self, s1, s2):
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            
            # Via U -> V (Track 0)
            e0_normal = Edge(u, v, EdgeType.NORMAL, 0)
            e0_inversa = Edge(v, u, EdgeType.NORMAL, 0) # La que ve de cara al Track 0

            # Via V -> U (Track 1)
            e1_normal = Edge(v, u, EdgeType.NORMAL, 1)
            e1_inversa = Edge(u, v, EdgeType.NORMAL, 1) # La que ve de cara al Track 1

            self.all_edges.extend([e0_normal, e0_inversa, e1_normal, e1_inversa])
            
            TrafficManager.register_segment(u.name, v.name, 0, e0_normal)
            TrafficManager.register_segment(v.name, u.name, 0, e0_inversa)
            TrafficManager.register_segment(v.name, u.name, 1, e1_normal)
            TrafficManager.register_segment(u.name, v.name, 1, e1_inversa)
            
            if v.id not in u.neighbors: u.neighbors[v.id] = []
            if u.id not in v.neighbors: v.neighbors[u.id] = []
            u.neighbors[v.id].extend([e0_normal, e1_inversa])
            v.neighbors[u.id].extend([e1_normal, e0_inversa])

    def _normalize_name(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        try:
            n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        except: pass
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        if raw is None: return None
        try:
            if isinstance(raw, float) and math.isnan(raw): return None
        except: return None
        
        s = str(raw).strip().replace('−', '-')
        digits = re.sub(r"[^0-9-]", "", s)
        try:
            val_int = int(digits)
            target, v_range = (41.5, (39.0, 44.0)) if is_lat else (2.0, (-1.0, 5.0))
            divisors = [10**i for i in range(10)]
            candidates = [val_int / d for d in divisors]
            hits = [c for c in candidates if v_range[0] <= c <= v_range[1]]
            return float(min(hits, key=lambda x: abs(x - target))) if hits else None
        except: return None

    # ############################################################################################
    # Mètodes Estàtics (Interfície Pública per Agents)
    # ############################################################################################

    @staticmethod
    def remove_train_from_edge(edge, train_id):
        if edge and edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    @staticmethod
    def register_segment(u_name, v_name, track_id, edge_object):
        TrafficManager._physical_segments[(u_name, v_name, track_id)] = edge_object

    @staticmethod
    def get_edge(u_name, v_name, track_id=0):
        return TrafficManager._physical_segments.get((u_name, v_name, track_id))
    
    @staticmethod
    def check_head_on_collision(my_edge, my_progress):
        """
        Versió ARREGLADA (Safe Version).
        Comprova si ve un tren de cara a la mateixa via física.
        Retorna: Distància en km (float). Si és segur, retorna float('inf').
        """
        # 1. Validacions bàsiques per evitar errors
        if not my_edge: return float('inf')
        
        # 2. Busquem la via inversa (el mateix segment físic però en sentit contrari)
        u_name, v_name = my_edge.node1.name, my_edge.node2.name
        
        # El track_id ha de ser el mateix per ser un perill "Frontal"
        inverse_edge = TrafficManager.get_edge(v_name, u_name, my_edge.track_id)
        
        # Si la via inversa no existeix, és segur
        if not inverse_edge: 
            return float('inf')
            
        # 3. Accés segur al diccionari de posicions (sense bucles)
        trains_inverse = TrafficManager._train_positions.get(inverse_edge)
        
        # Si no hi ha llista o està buida, no hi ha perill
        if not trains_inverse:
            return float('inf')

        # 4. Càlcul de col·lisió directe (Sense iterar)
        # trains_inverse està ordenada per progrés descendent: el [0] és el més avançat
        # i per tant l'únic que ens pot xocar de cara primer.
        enemy_id, enemy_prog = trains_inverse[0] 
        
        # Col·lisionen si: (El meu Progrés des de U) + (El seu Progrés des de V) >= 1.0
        gap_percent = 1.0 - (my_progress + enemy_prog)
        
        # Convertim percentatge a KM
        dist_km = gap_percent * my_edge.real_length_km
        
        return dist_km

    @staticmethod
    def check_alert(u_name, v_name, track_id):
        return 1 if (u_name, v_name, track_id) in TrafficManager._reported_obstacles else 0
    
    @staticmethod
    def get_safe_track(u_name, v_name):
        """
        Busca una vía libre (0 o 1) para ir de u_name a v_name.
        Retorna el track_id seguro o None si todas están ocupadas/peligrosas.
        """
        # Probamos las dos posibles vías (0 y 1)
        possible_tracks = [0, 1]
        
        # Opcional: Si quieres priorizar la vía 1 para adelantamientos, cambia el orden
        # possible_tracks = [0, 1] 
        
        for t_id in possible_tracks:
            # 1. Obtenemos el objeto vía candidato
            edge = TrafficManager.get_edge(u_name, v_name, t_id)
            if not edge: continue # Si no existe (ej. tramo de vía única), pasamos
            
            # 2. Comprobamos PELIGRO FRONTAL (Tren viniendo de cara)
            # Simulamos que estamos al inicio (progress=0.0)
            dist_threat = TrafficManager.check_head_on_collision(edge, 0.0)
            
            # Si la distancia es infinita (no hay nadie) o muy grande (>5km), es segura
            if dist_threat == float('inf') or dist_threat > 5.0:
                
                # 3. (Opcional) Comprobar congestión en el mismo sentido
                # Para evitar entrar si hay un tren justo delante parado
                trains_same_dir = TrafficManager._train_positions.get(edge, [])
                if trains_same_dir:
                    last_train_id, last_prog = trains_same_dir[-1] # El último que entró
                    # Si el último tren está a menos del 5% del recorrido, esperamos para no bloquear
                    if last_prog < 0.05: 
                        continue 

                return t_id # Encontramos una vía segura
                 
        return None # Ninguna vía es segura, hay que esperar
    
    @staticmethod
    def report_issue(u_name, v_name, track_id):
        TrafficManager._reported_obstacles[(u_name, v_name, track_id)] = "ALERT"

    @staticmethod
    def update_train_position(edge, train_id, progress):
        if not edge: return
        
        # Inicialització segura
        if edge not in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = []
        
        # Actualització neta
        current_list = TrafficManager._train_positions[edge]
        # Filtrem el propi tren si ja hi era (per actualitzar dada)
        new_list = [(tid, p) for tid, p in current_list if tid != train_id]
        
        # Afegim posició nova
        new_list.append((train_id, progress))
        
        # Ordenem: El que té més progrés (més a prop de sortir) va primer
        new_list.sort(key=lambda x: x[1], reverse=True)
        
        TrafficManager._train_positions[edge] = new_list

    @staticmethod
    def remove_train(train_id):
        keys = list(TrafficManager._train_positions.keys())
        for edge in keys:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    @staticmethod
    def get_distance_to_leader(edge, my_train_id):
        if not edge or edge not in TrafficManager._train_positions:
            return float('inf')
        
        trains_on_edge = TrafficManager._train_positions[edge]
        if not trains_on_edge: return float('inf')
        
        # Busquem el nostre index
        my_idx = -1
        for i, (tid, prog) in enumerate(trains_on_edge):
            if tid == my_train_id:
                my_idx = i
                break
        
        # Si no ens trobem (error sync) o som els primers (index 0), ningú davant
        if my_idx <= 0:
            return float('inf')
            
        # El líder és qui està just abans a la llista (index - 1)
        leader_id, leader_prog = trains_on_edge[my_idx - 1]
        _, my_prog = trains_on_edge[my_idx]
        
        dist_km = (leader_prog - my_prog) * edge.real_length_km
        return max(0.0, dist_km) # Mai retornar negatiu per error de float

    # ==========================================
    # UTILITATS I DEBUG
    # ==========================================

    def save_brain(self):
        self.brain.save_table("Agent/Qtables/q_table.pkl")

    def debug_network_snapshot(self):
        print(f"\n=== SNAPSHOT XARXA (T={self.sim_time:.1f}) ===")
        print(f"Total Trens Actius: {len(self.active_trains)}")
        
        obstacles = len(self._reported_obstacles)
        if obstacles > 0:
            print(f" ALERTA: Hi ha {obstacles} segments amb incidències reportades!")

        print("--- LLISTA DE TRENS ---")
        for t in self.active_trains:
            if not t.finished and t.node:
                delay = t.calculate_delay()
                dest_name = t.target.name if t.target else "Fi"
                seg = f"{t.node.name[:8]}->{dest_name[:8]}"
                print(f"{t.id % 1000:03d} | {seg:18} | v={t.current_speed:5.1f} | Delay: {delay:+5.1f}m")
        print("==========================================\n")