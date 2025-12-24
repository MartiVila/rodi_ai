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

class TrafficManager:
    """
    Centralitza l'estat de la xarxa i la gestió dels trens.
    Ara conté: Nodes, Vies, Trens i Lògica de Spawn.
    """
    # Estàtics per accés ràpid des dels trens (com tenies abans)
    _reported_obstacles = {}
    _train_positions = {}
    _physical_segments = {} 
    
    # Configuració de Temps (moguda aquí)
    SPAWN_INTERVAL = 30  
    RESET_INTERVAL = 210
    CHAOS_INTERVAL = 60

    def __init__(self, width=1400, height=900, is_training=False):
        self.is_training = is_training 
        self.nodes = {}
        self.all_edges = []
        self.lines = {}
        self.active_trains = []
        
        # Dimensions per escalar el mapa (necessari per load_real_data)
        self.width = width
        self.height = height

        # Timers interns
        self.sim_time = 0.0
        self.last_spawn = -999 # Perquè surti un de seguida
        self.last_reset = 0
        self.last_chaos = 0

        # Inicialitzem l'Agent compartit
        self.brain = QLearningAgent(epsilon=0.2)
        try:
            self.brain.load_table("Agent/Qtables/q_table.pkl")
        except:
            print("No s'ha trobat taula prèvia, es crearà una nova.")

        # Carreguem el mapa automàticament en iniciar
        self._load_network()

    # ==========================================
    # LÒGICA PRINCIPAL (UPDATE)
    # ==========================================
    def update(self, dt_minutes):
        """
        Mètode principal que RodaliesAI cridarà a cada frame.
        """
        self.sim_time += dt_minutes

        # 1. Gestió d'Events (Resets i Caos)
        self._handle_mechanics()

        # 2. Spawning (Creació de trens)
        if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
            self.last_spawn = self.sim_time
            self.spawn_line_train('R1_NORD')

        # 3. Actualització de Trens
        # Fem servir una còpia de la llista per poder esborrar mentre iterem
        for t in self.active_trains[:]:
            t.update(dt_minutes)
            if t.finished:
                self.remove_train(t.id)
                self.active_trains.remove(t)

    def _handle_mechanics(self):
        """Gestió interna de resets i obstacles"""
        # Reset diari
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            self.reset_network_status()
            print(f"[TrafficManager] Manteniment de vies realitzat al minut {int(self.sim_time)}")

        # Caos (Obstacles)
        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()
                    # Nota: No fem report_issue aquí, deixem que els trens ho descobreixin

    def reset_network_status(self):
        """Neteja obstacles i alertes"""
        for e in self.all_edges: 
            e.edge_type = EdgeType.NORMAL
            e.update_properties()
        TrafficManager._reported_obstacles.clear()

    # ==========================================
    # GESTIÓ DE TRENS
    # ==========================================
    def spawn_line_train(self, line_name):
        # Importem Train aquí per evitar l'error circular que tenies
        from Enviroment.Train import Train

        if line_name not in self.lines: return
        station_names = self.lines[line_name]
        
        # Convertim noms a objectes Node
        route_nodes = [self.nodes[n] for n in station_names if n in self.nodes]
        
        if len(route_nodes) > 1:
            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            
            # Passem el flag is_training al tren nou
            new_train = Train(self.brain, route_nodes, schedule, self.sim_time, 
                              is_training=self.is_training) 
            self.active_trains.append(new_train)    

    def calculate_schedule(self, route_nodes, start_time):
        schedule = {}
        current_time = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        
        for i in range(len(route_nodes) - 1):
            u_name = route_nodes[i].name
            v_name = route_nodes[i+1].name
            edge = self.get_edge(u_name, v_name)
            
            travel_time = 3.0 # Default
            if edge: travel_time = edge.expected_minutes
            
            current_time += travel_time
            schedule[route_nodes[i+1].id] = current_time
        return schedule

    # ==========================================
    # CARREGA DE DADES (Mogut des de RodaliesAI)
    # ==========================================
    def _normalize_name(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        # ... (Codi idèntic al que tenies a RodaliesAI) ...
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
        
        # 1. Carregar Nodes
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
            # Escalat usant self.width/height passats al init
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * (self.width - 100) + 50
            y = self.height - (((st['lat'] - min_lat) / (max_lat - min_lat)) * (self.height - 100) + 50)
            
            node = Node(x, y, st['id'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            self.nodes[st['norm']] = node

        # 2. Carregar Vies (Edges)
        for s1, s2 in Datas.R1_CONNECTIONS: 
            self._add_connection(s1, s2)
            
        # 3. Definir Linies
        self.lines['R1_NORD'] = Datas.R1_STA
        self.lines['R1_SUD'] = Datas.R1_STA[::-1]
        
        print(f"[TrafficManager] Xarxa carregada: {len(self.nodes)} estacions, {len(self.all_edges)} vies.")

    def _add_connection(self, s1, s2):
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            
            # Creem via física d'anada (track 0) i tornada (track 1)
            e0 = Edge(u, v, EdgeType.NORMAL, 0)
            e1 = Edge(v, u, EdgeType.NORMAL, 1) # Note: v -> u for return
            
            self.all_edges.extend([e0, e1])
            
            # Registrem al sistema estàtic per accés ràpid
            TrafficManager.register_segment(u.name, v.name, e0)
            TrafficManager.register_segment(v.name, u.name, e1)
            
            # Registrem veïns (opcional si usem rutes fixes, però útil per debug)
            u.neighbors[v.id] = [e0]
            v.neighbors[u.id] = [e1]

    # ==========================================
    # STATIC METHODS (Interfície per als trens)
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
        # Eliminem anterior i afegim nou
        TrafficManager._train_positions[edge] = [
            (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
        ]
        TrafficManager._train_positions[edge].append((train_id, progress))
        # Ordenem
        TrafficManager._train_positions[edge].sort(key=lambda x: x[1], reverse=True)

    @staticmethod
    def remove_train(train_id):
        for edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    # Mètode auxiliar per salvar el cervell en tancar
    def save_brain(self):
        self.brain.save_table("Agent/Qtables/q_table.pkl")




    #--------------------------DEBUG-----------------------------------
    def debug_network_snapshot(self):
        """
        Imprimeix un resum de tots els trens actius.
        Útil per cridar cada X segons o amb una tecla.
        """
        print(f"\n=== SNAPSHOT XARXA (T={self.sim_time:.1f}) ===")
        print(f"Total Trens Actius: {len(self.active_trains)}")
        
        obstacles = len(self._reported_obstacles)
        if obstacles > 0:
            print(f"⚠️  ALERTA: Hi ha {obstacles} segments amb incidències reportades!")

        print("--- LLISTA DE TRENS ---")
        for t in self.active_trains:
            # Usem el mètode calculate_delay del tren
            delay = t.calculate_delay()
            seg = f"{t.node.name[:10]}->{t.target.name[:10]}" if t.target else "Fi Trayecte"
            print(f"🚄 {t.id % 1000:03d} | {seg:25} | v={t.current_speed:5.1f} | Delay: {delay:+5.1f}m")
        print("==========================================\n")