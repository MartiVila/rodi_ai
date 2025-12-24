import pandas as pd
import math
import random
import unicodedata
import re
from geopy.distance import great_circle

# Imports propis
from Agent.QlearningAgent import QLearningAgent
from Enviroment.Datas import Datas
from Enviroment.Node import Node
from Enviroment.Edge import Edge
from Enviroment.EdgeType import EdgeType
    # Assegura't que tens l'import
from Enviroment.Datas import Datas

class TrafficManager:
    """
    Centralitza l'estat de la xarxa i la gestió dels trens.
    Ara conté: Nodes, Vies, Trens i Lògica de Spawn.
    """
    # Estàtics per accés ràpid des dels trens
    _reported_obstacles = {}
    _train_positions = {}
    _physical_segments = {} 
    
    # Configuració de Temps
    SPAWN_INTERVAL = 30  
    RESET_INTERVAL = 210
    CHAOS_INTERVAL = 60

    def __init__(self, width=1400, height=900, is_training=False):
        self.is_training = is_training 
        self.nodes = {}
        self.all_edges = []
        self.lines = {}
        self.active_trains = []
        
        self.width = width
        self.height = height

        self.sim_time = 0.0
        self.last_spawn = -999 
        self.last_reset = 0
        self.last_chaos = 0
        self.completed_train_logs = []

        self.brain = QLearningAgent(epsilon=0.2)
        try:
            self.brain.load_table("Agent/Qtables/q_table.pkl")
        except:
            print("No s'ha trobat taula prèvia, es crearà una nova.")

        self._load_network()

    # ==========================================
    # LÒGICA PRINCIPAL (UPDATE)
    # ==========================================
    def update(self, dt_minutes):
        self.sim_time += dt_minutes
        self._handle_mechanics()

        if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
            self.last_spawn = self.sim_time
            self.spawn_line_train('R1_NORD')

        for t in self.active_trains[:]:
            t.update(dt_minutes)
            if t.finished:
                # [NOU] Abans d'esborrar, guardem l'informe
                self._archive_train_log(t)
                
                self.remove_train(t.id)
                self.active_trains.remove(t)

    def _archive_train_log(self, train):
        """Guarda les dades del viatge per a l'informe"""
        log_entry = {
            'id': train.id,
            'schedule': train.schedule.copy(),      # {node_id: expected_time}
            'actuals': train.arrival_logs.copy(),   # {station_name: actual_time}
            'route_map': {n.id: n.name for n in train.route_nodes} # Per mapejar ID->Nom
        }
        self.completed_train_logs.append(log_entry)

    def _handle_mechanics(self):
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            self.reset_network_status()
            #print(f"[TrafficManager] Manteniment de vies realitzat al minut {int(self.sim_time)}")

        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
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

    # ==========================================
    # GESTIÓ DE TRENS (CORREGIT)
    # ==========================================
    def spawn_line_train(self, line_name):
        from Enviroment.Train import Train # Import local per evitar cicle

        if line_name not in self.lines: return
        station_names_raw = self.lines[line_name]
        
        # [CORRECCIÓ CLAU] Normalitzem el nom abans de buscar al diccionari de nodes
        route_nodes = []
        for name_raw in station_names_raw:
            name_norm = self._normalize_name(name_raw)
            if name_norm in self.nodes:
                route_nodes.append(self.nodes[name_norm])
        
        # Ara route_nodes tindrà totes les estacions correctes, inclosa L'Hospitalet
        if len(route_nodes) > 1:
            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            
            new_train = Train(self.brain, route_nodes, schedule, self.sim_time, 
                              is_training=self.is_training) 
            self.active_trains.append(new_train)
            if not self.is_training:
                print(f"[Spawn] Tren creat a {route_nodes[0].name} cap a {route_nodes[-1].name}")



    def calculate_schedule(self, route_nodes, start_time):
        schedule = {}
        current_time = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        
        for i in range(len(route_nodes) - 1):
            u_name = route_nodes[i].name
            v_name = route_nodes[i+1].name
            edge = self.get_edge(u_name, v_name)
            
            travel_time = 3.0 
            if edge: travel_time = edge.expected_minutes
            
            # [CORRECCIÓ] Sumem el temps de viatge + el temps que s'ha estat aturat a l'estació 'i'
            current_time += travel_time + Datas.STOP_STA_TIME
            
            schedule[route_nodes[i+1].id] = current_time
        return schedule
    # ==========================================
    # CARREGA DE DADES
    # ==========================================
    def _normalize_name(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        if raw is None or (isinstance(raw, float) and math.isnan(raw)): return None
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

    def _load_network(self):
        print("[TrafficManager] Carregant xarxa ferroviària...")
        
        wanted_stations = set()
        for s1, s2 in Datas.R1_CONNECTIONS:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        try:
            df = pd.read_csv('Enviroment/data/estaciones_coordenadas.csv', sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception as e:
            print(f"[Error] No s'ha pogut llegir el CSV: {e}")
            return

        lats, lons, temp_st = [], [], []
        for _, row in df.iterrows():
            name = row.get('NOMBRE_ESTACION')
            norm_name = self._normalize_name(name)
            if norm_name not in wanted_stations: continue 

            lat = self._parse_coord(row.get('LATITUD'), True)
            lon = self._parse_coord(row.get('LONGITUD'), False)
            
            if name and lat and lon:
                temp_st.append({'id': str(row.get('ID')), 'norm': norm_name, 'orig': name, 'lat': lat, 'lon': lon})
                lats.append(lat)
                lons.append(lon)

        if not lats: return
        min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)

        for st in temp_st:
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * (self.width - 100) + 50
            y = self.height - (((st['lat'] - min_lat) / (max_lat - min_lat)) * (self.height - 100) + 50)
            
            node = Node(x, y, st['id'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            self.nodes[st['norm']] = node

        for s1, s2 in Datas.R1_CONNECTIONS: 
            self._add_connection(s1, s2)
            
        self.lines['R1_NORD'] = Datas.R1_STA
        self.lines['R1_SUD'] = Datas.R1_STA[::-1]
        
        print(f"[TrafficManager] Xarxa carregada: {len(self.nodes)} estacions, {len(self.all_edges)} vies.")

    def _add_connection(self, s1, s2):
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            e0 = Edge(u, v, EdgeType.NORMAL, 0)
            e1 = Edge(v, u, EdgeType.NORMAL, 1)
            self.all_edges.extend([e0, e1])
            TrafficManager.register_segment(u.name, v.name, e0)
            TrafficManager.register_segment(v.name, u.name, e1)
            u.neighbors[v.id] = [e0]
            v.neighbors[u.id] = [e1]

    # ==========================================
    # STATIC METHODS
    # ==========================================
    @staticmethod
    def register_segment(u_name, v_name, edge_object):
        TrafficManager._physical_segments[(u_name, v_name)] = edge_object

    @staticmethod
    def get_edge(u_name, v_name):
        return TrafficManager._physical_segments.get((u_name, v_name))
    
    @staticmethod
    def check_alert(u_name, v_name, track_id):
        return 1 if (u_name, v_name, track_id) in TrafficManager._reported_obstacles else 0
    
    @staticmethod
    def report_issue(u_name, v_name, track_id):
        TrafficManager._reported_obstacles[(u_name, v_name, track_id)] = "ALERT"

    @staticmethod
    def update_train_position(edge, train_id, progress):
        if not edge: return
        if edge not in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = []
        TrafficManager._train_positions[edge] = [
            (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
        ]
        TrafficManager._train_positions[edge].append((train_id, progress))
        TrafficManager._train_positions[edge].sort(key=lambda x: x[1], reverse=True)

    @staticmethod
    def remove_train(train_id):
        for edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    def save_brain(self):
        self.brain.save_table("Agent/Qtables/q_table.pkl")

    #--------------------------DEBUG-----------------------------------
    def debug_network_snapshot(self):
        print(f"\n=== SNAPSHOT XARXA (T={self.sim_time:.1f}) ===")
        print(f"Total Trens Actius: {len(self.active_trains)}")
        
        obstacles = len(self._reported_obstacles)
        if obstacles > 0:
            print(f"⚠️  ALERTA: Hi ha {obstacles} segments amb incidències reportades!")

        print("--- LLISTA DE TRENS ---")
        for t in self.active_trains:
            delay = t.calculate_delay()
            seg = f"{t.node.name[:10]}->{t.target.name[:10]}" if t.target else "Fi Trayecte"
            print(f"🚄 {t.id % 1000:03d} | {seg:25} | v={t.current_speed:5.1f} | Delay: {delay:+5.1f}m")
        print("==========================================\n")