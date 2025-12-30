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
    
    # Estat compartit
    _reported_obstacles = {}
    _train_positions = {}
    _physical_segments = {}
    
    # Configuració
    SPAWN_INTERVAL = 15    
    #cada 2 hores rotació de vies en obstacle
    RESET_INTERVAL = 120   
    CHAOS_INTERVAL = 120    

    def __init__(self, width=1400, height=900, is_training=False):
        self.is_training = is_training

        #Esta hardcoded, es podria calcular segons la mida de la pantalla
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

        # Cervell
        self.brain = QLearningAgent(
            alpha=DEFAULT_AGENT_PARAMS[0], 
            gamma=DEFAULT_AGENT_PARAMS[1], 
            epsilon=DEFAULT_AGENT_PARAMS[2]
        )
        try:
            self.brain.load_table("Agent/Qtables/q_table.pkl")
            if not self.is_training:
                print("(TrafficManager) Cervell (Q-Table) carregat correctament.")
        except Exception:
            print("(TrafficManager) No s'ha trobat taula prèvia. Iniciant des de zero.")

        self._load_network()


    #Bucle principal
    def update(self, dt_minutes):
        self.sim_time += dt_minutes
        self._handle_mechanics()

        # SPAWN
        if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
            self.last_spawn = self.sim_time

            # Decidim línia segons mode         
            if self.is_training:
                line_anada = self.current_spawn_line
                line_tornada = f"{self.current_spawn_line}_SUD"
            else:
                line_anada = 'R1_NORD'
                line_tornada = 'R1_SUD'

            # Spawn trens
            self.spawn_line_train(line_anada)
            if line_tornada in self.lines:
                self.spawn_line_train(line_tornada)

        # Update trens actius
        for t in self.active_trains[:]:
            t.update(dt_minutes)
            
            # Si acaba el tren, eliminem-lo
            if t.finished:
                self._archive_train_log(t)
                self.remove_train(t.id) 
                self.active_trains.remove(t)

    def _handle_mechanics(self):
        # Manteniment (Reparació automàtica)
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            self.reset_network_status()

        # Caos avaries aleatòries
        if not self.is_training and (self.sim_time - self.last_chaos > self.CHAOS_INTERVAL):
            self.last_chaos = self.sim_time
            
            # Busquem vies que estiguin sanes (NORMAL)
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            
            if len(normals) > 0:
                # Triem 1 segment aleatori per trencar
                target_edge = random.choice(normals)
                
                # Trenquem la direcció original (A -> B)
                target_edge.edge_type = EdgeType.OBSTACLE
                target_edge.update_properties()
                TrafficManager.report_issue(target_edge.node1.name, target_edge.node2.name, target_edge.track_id)
                
                # Trenquem la direcció inversa (B -> A)
                # Busquem la via que connecta els mateixos nodes al revés amb el mateix track_id
                inverse_edge = TrafficManager.get_edge(target_edge.node2.name, target_edge.node1.name, target_edge.track_id)
                
                if inverse_edge:
                    inverse_edge.edge_type = EdgeType.OBSTACLE
                    inverse_edge.update_properties()
                    TrafficManager.report_issue(inverse_edge.node1.name, inverse_edge.node2.name, inverse_edge.track_id)
                    
                print(f"(CAOS) Avaria a la via {target_edge.node1.name}-{target_edge.node2.name} (Via {target_edge.track_id})")
    
    # Reset cada 2 hores
    def reset_network_status(self):
        for e in self.all_edges: 
            e.edge_type = EdgeType.NORMAL
            e.update_properties()
        TrafficManager._reported_obstacles.clear()


    def spawn_line_train(self, line_name):
        from Enviroment.Train import Train 

        if line_name not in self.lines: return
        
        station_names_raw = self.lines[line_name]
        route_nodes = []
        for name_raw in station_names_raw:
            name_norm = self._normalize_name(name_raw)
            if name_norm in self.nodes:
                route_nodes.append(self.nodes[name_norm])
        
        starting_track = 1 if "SUD" in line_name else 0

        if len(route_nodes) > 1:
            # Evitem fer spawn si la via de sortida està ocupada per prevenir xocs immediats.
            start_node_name = route_nodes[0].name
            next_node_name = route_nodes[1].name
            
            start_edge = TrafficManager.get_edge(start_node_name, next_node_name, starting_track)
            
            if start_edge:
                # Comprovem congestió al davant
                trains_on_edge = TrafficManager._train_positions.get(start_edge, [])
                if trains_on_edge:
                    # La llista està ordenada per progrés (més avançat primer). 
                    # L'últim és el que acaba d'entrar (progrés proper a 0).
                    _, last_progress = trains_on_edge[-1]
                    
                    # Si l'últim tren està a menys del 5% del tram, no sortim encara.
                    if last_progress < 0.05:
                        return 

                # 2. Comprovem col·lisió frontal
                dist_threat = TrafficManager.check_head_on_collision(start_edge, 0.0)
                if dist_threat < 3.0: # Si ve un tren de cara a menys de 3km
                    # No fem spawn per evitar col·lisió immediata
                    return

            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            
            new_train = Train(
                agent=self.brain, 
                route_nodes=route_nodes, 
                schedule=schedule, 
                start_time_sim=self.sim_time, 
                is_training=self.is_training,
                prefered_track=starting_track
            )
            
            self.active_trains.append(new_train)
            if not self.is_training:
                # Print per debug
                print(f"(Spawn) Tren {new_train.id} sortint de {route_nodes[0].name} (Via {starting_track})")

    def calculate_schedule(self, route_nodes, start_time):
        """
        Genera l'horari basant-se en els temps oficials de Renfe (Datas.py).
        Això elimina els càlculs físics erronis i posa objectius reals.
        """
        schedule = {}
        current_time = start_time
        
        # El primer node és l'origen, hora = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        
        for i in range(len(route_nodes) - 1):
            u_name = route_nodes[i].name
            v_name = route_nodes[i+1].name
            
            # Obtenim el temps real de l'horari
            official_travel_time = Datas.get_travel_time(u_name, v_name)
            
            # Afegim l'aturada tècnica (els horaris ja solen incloure part d'això,
            # però per la IA li donem el temps de viatge + parada)
            # Aquí sumem: Temps Viatge + Parada Estació.
            current_time += official_travel_time + Datas.STOP_STA_TIME
            
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

    #Carregar de dades externes
    def _load_network(self):
        print("(TrafficManager) Carregant xarxa ferroviària...")
        
        wanted_stations = set()
        for s1, s2 in Datas.R1_CONNECTIONS:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception as e:
            print(f"Error: no es pot llegir {csv_path}: {e}")
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
            print("Error: No s'han trobat estacions vàlides.")
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
        
        print(f"(TrafficManager) Xarxa construïda: {len(self.nodes)} estacions, {len(self.all_edges)} vies.")

    # Afegir connexió bidireccional entre dos nodes
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

    # Metodes estàtics per a la gestió global de trens i vies

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
        Comprova si ve un tren de cara a la mateixa vía física (mateix track_id).
        Retorna: Distància en km (float). Si és segur, retorna float('inf').
        """
        # Validacions bàsiques per evitar errors
        if not my_edge: return float('inf')
        
        # Busquem la via inversa (el mateix segment físic però en sentit contrari)
        u_name, v_name = my_edge.node1.name, my_edge.node2.name
        
        # En la representació actual:
        # - Track 0 en direcció U->V correspon a Track 0 en direcció V->U
        # - Track 1 en direcció U->V correspon a Track 1 en direcció V->U
        inverse_edge = TrafficManager.get_edge(v_name, u_name, my_edge.track_id)
        
        if not inverse_edge: 
            return float('inf')
            
        # Accés al diccionari de posicions
        trains_inverse = TrafficManager._train_positions.get(inverse_edge)
        
        # Si no hi ha llista o està buida, no hi ha perill
        if not trains_inverse:
            return float('inf')

        # Càlcul de col·lisió directe (Sense iterar)
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
        Busca una vía lliure (0 o 1) per anar de u_name a v_name.
        Retorna el track_id segur o None si totes estan ocupades/peligroses.
        """
        # Probem les dues vies disponibles
        possible_tracks = [0, 1]
        

        # possible_tracks = [0, 1]
        
        for t_id in possible_tracks:
            # Obtenim l'objecte via candidat
            edge = TrafficManager.get_edge(u_name, v_name, t_id)
            if not edge: continue # Si no existeix (tram de via única), passem
            
            # Ignorar si la via està marcada com a OBSTACLE
            try:
                if edge.edge_type == EdgeType.OBSTACLE:
                    continue
            except Exception:
                pass

            # Comprovem perill frontal (Tren venint de cara)
            # Simulem que estem a l'inici (progress=0.0)
            dist_threat = TrafficManager.check_head_on_collision(edge, 0.0)
            
            # Si la distància és infinita (no hi ha ningú) o molt gran (>5km), és segura
            if dist_threat == float('inf') or dist_threat > 5.0:
                
                # Comprovar congestió en el mateix sentit
                # Per evitar entrar si hi ha un tren just davant parat
                trains_same_dir = TrafficManager._train_positions.get(edge, [])
                if trains_same_dir:
                    last_train_id, last_prog = trains_same_dir[-1] # L'últim que va entrar
                    # Si l'últim tren està a menys del 5% del recorregut, esperem per no bloquejar
                    if last_prog < 0.05: 
                        continue 

                return t_id # Via segura trobada
                 
        return None # Cap via és segura, esperar
    
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


    def save_brain(self):
        self.brain.save_table("Agent/Qtables/q_table.pkl")

    # Mètodes de debug
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