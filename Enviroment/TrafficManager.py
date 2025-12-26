import pandas as pd
import math
import random
import unicodedata
import re
# from geopy.distance import great_circle # (Opcional si es vol fer servir distància real)

# Imports del projecte
from Agent.QlearningAgent import QLearningAgent
from Enviroment.Datas import Datas
from Enviroment.Node import Node
from Enviroment.Edge import Edge
from Enviroment.EdgeType import EdgeType

# Valors per defecte si no es troba un cervell entrenat
DEFAULT_AGENT_PARAMS = [0.7, 0.99, 0.99]  # Alpha, Gamma, Epsilon

class TrafficManager:
    """
    Classe central del Model (MVC). Actua com a 'Singleton' de facto per gestionar 
    l'estat global de la simulació ferroviària.
    
    Responsabilitats:
    1. Carregar i construir el graf de la xarxa (Nodes i Vies).
    2. Gestionar el cicle de vida dels trens (Spawn, Update, Despawn).
    3. Controlar la mecànica del món (Temps, Incidències, Manteniment).
    4. Proporcionar una interfície estàtica d'accés ràpid per als agents (Trens).
    """
    
    # === ESTAT COMPARTIT (Shared Memory) ===
    # Diccionaris estàtics per permetre accés O(1) des dels trens sense passar referències constants
    _reported_obstacles = {}       # {(node_u, node_v, track_id): "ALERT"}
    _train_positions = {}          # {Edge: [(train_id, progress), ...]}
    _physical_segments = {}        # {(node_u_name, node_v_name): EdgeObject}
    
    # === CONFIGURACIÓ DE SIMULACIÓ ===
    SPAWN_INTERVAL = 30    # Minuts entre sortida de trens
    RESET_INTERVAL = 210   # Minuts per netejar incidències (Manteniment)
    CHAOS_INTERVAL = 60    # Minuts entre generació d'obstacles aleatoris

    def __init__(self, width=1400, height=900, is_training=False):
        """
        Inicialitza el gestor de trànsit.
        
        :param width: Amplada del mapa (per escalar coordenades).
        :param height: Alçada del mapa.
        :param is_training: Si és True, desactiva logs i visuals pesats.
        """
        self.is_training = is_training 
        self.width = width
        self.height = height

        # Estructures de Dades Dinàmiques
        self.nodes = {}
        self.all_edges = []
        self.lines = {}
        self.active_trains = []
        self.completed_train_logs = []

        # Estat del Temps
        self.sim_time = 0.0
        self.last_spawn = -999 
        self.last_reset = 0
        self.last_chaos = 0
        
        # Configuració de Spawn
        self.current_spawn_line = 'R1_NORD' 

        # === CERVELL (Agent Compartit) ===
        # Tots els trens comparteixen la mateixa taula Q per aprendre col·lectivament
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

        # Construcció del Món
        self._load_network()

    """
    ############################################################################################
    ############################################################################################

    Bucle Principal (UPDATE & MECHANICS)

    ############################################################################################
    ############################################################################################
    """

    def update(self, dt_minutes):
        """
        Avança l'estat de la simulació un pas de temps.
        
        :param dt_minutes: Delta time en minuts simulats.
        """
        self.sim_time += dt_minutes
        
        # 1. Esdeveniments de l'entorn (Caos, Manteniment)
        self._handle_mechanics()

        # 2. Generació de nous trens (Spawning)
        if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
            self.last_spawn = self.sim_time
            self.spawn_line_train(self.current_spawn_line)

        # 3. Actualització de trens actius
        # Itera sobre una còpia ([:]) per permetre esborrat segur
        for t in self.active_trains[:]:
            t.update(dt_minutes)
            
            if t.finished:
                self._archive_train_log(t)
                self.remove_train(t.id) # Neteja del registre estàtic
                self.active_trains.remove(t)

    def _handle_mechanics(self):
        """Gestiona els esdeveniments automàtics de l'entorn."""
        
        # A. Manteniment (Reset periòdic d'incidències)
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            self.reset_network_status()
            # if not self.is_training: print(f"[Manteniment] Vies reparades al minut {int(self.sim_time)}")

        # B. Caos (Generació d'obstacles)
        # Només en mode visual/debug, per no alterar mètriques pures d'entrenament si no es vol
        if not self.is_training and (self.sim_time - self.last_chaos > self.CHAOS_INTERVAL):
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            
            # Trenquem 2 vies aleatòries
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()
                    # Nota: No reportem l'obstacle aquí. Els trens se l'han de trobar.

    def reset_network_status(self):
        """Repara totes les vies i neteja els reports d'incidències."""
        for e in self.all_edges: 
            e.edge_type = EdgeType.NORMAL
            e.update_properties()
        TrafficManager._reported_obstacles.clear()

    """
    ############################################################################################
    ############################################################################################

    Gestió de Trens (Spawn & Schedule)

    ############################################################################################
    ############################################################################################
    """

    def spawn_line_train(self, line_name):
        """
        Crea un nou tren assignat a una línia específica.
        
        :param line_name: Clau del diccionari self.lines (ex: 'R1_NORD').
        """
        # Import local per evitar cicle: Train importa TrafficManager
        from Enviroment.Train import Train 

        if line_name not in self.lines: return
        
        station_names_raw = self.lines[line_name]
        
        # Convertim noms de llista a objectes Node existents
        route_nodes = []
        for name_raw in station_names_raw:
            name_norm = self._normalize_name(name_raw)
            if name_norm in self.nodes:
                route_nodes.append(self.nodes[name_norm])
        
        # Validació mínima: ruta de com a mínim 2 estacions
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
        """
        Calcula l'horari previst (ideal) per a un tren.
        
        :return: Diccionari {node_id: temps_arribada_minuts}.
        """
        schedule = {}
        current_time = start_time
        
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        
        for i in range(len(route_nodes) - 1):
            u_name = route_nodes[i].name
            v_name = route_nodes[i+1].name
            
            # Obtenim la via física per saber la durada ideal
            edge = self.get_edge(u_name, v_name)
            travel_time = edge.expected_minutes if edge else 3.0
            
            # Temps total = Viatge + Parada estació anterior
            current_time += travel_time + Datas.STOP_STA_TIME
            
            schedule[route_nodes[i+1].id] = current_time
            
        return schedule

    def _archive_train_log(self, train):
        """Guarda les estadístiques d'un tren que ha finalitzat per a l'informe final."""
        log_entry = {
            'id': train.id,
            'schedule': train.schedule.copy(),      # {node_id: expected_time}
            'actuals': train.arrival_logs.copy(),   # {station_name: actual_time}
            'route_map': {n.id: n.name for n in train.route_nodes} # Per traduir IDs després
        }
        self.completed_train_logs.append(log_entry)

    """
    ############################################################################################
    ############################################################################################

    Càrrega de Dades (CSV & Graph Building)

    ############################################################################################
    ############################################################################################
    """

    def _load_network(self):
        """
        Llegeix el fitxer CSV d'estacions i construeix el graf (Nodes i Vies).
        Utilitza Datas.R1_CONNECTIONS per definir la topologia.
        """
        print("[TrafficManager] Carregant xarxa ferroviària...")
        
        # 1. Identificar quines estacions necessitem (només R1)
        wanted_stations = set()
        for s1, s2 in Datas.R1_CONNECTIONS:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        # 2. Llegir CSV
        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception as e:
            print(f"[Error CRÍTIC] No s'ha pogut llegir {csv_path}: {e}")
            return

        # 3. Processar coordenades i crear objectes temporals
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

        # 4. Normalitzar coordenades per encaixar a la pantalla (Screen Space)
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        margin = 100
        # Mapeig de Lat/Lon -> X/Y píxels
        for st in temp_st:
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * (self.width - margin) + 50
            y = self.height - (((st['lat'] - min_lat) / (max_lat - min_lat)) * (self.height - margin) + 50)
            
            node = Node(x, y, st['id'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            
            self.nodes[st['norm']] = node

        # 5. Crear connexions (Vies)
        for s1, s2 in Datas.R1_CONNECTIONS: 
            self._add_connection(s1, s2)
            
        # 6. Definir línies lògiques
        self.lines['R1_NORD'] = Datas.R1_STA
        self.lines['R1_SUD'] = Datas.R1_STA[::-1]
        
        print(f"[TrafficManager] Xarxa construïda: {len(self.nodes)} estacions, {len(self.all_edges)} vies.")

    def _add_connection(self, s1, s2):
        """Crea una doble via (anada i tornada) entre dues estacions."""
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            
            # Via U -> V (Track 0)
            e0 = Edge(u, v, EdgeType.NORMAL, 0)
            # Via V -> U (Track 1)
            e1 = Edge(v, u, EdgeType.NORMAL, 1)
            
            self.all_edges.extend([e0, e1])
            
            # Registre al diccionari de segments físics
            TrafficManager.register_segment(u.name, v.name, e0)
            TrafficManager.register_segment(v.name, u.name, e1)
            
            # Connexió lògica del graf
            u.neighbors[v.id] = [e0]
            v.neighbors[u.id] = [e1]

    def _normalize_name(self, name):
        """Neteja strings per fer-los claus de diccionari robustes (sense accents, espais, etc)."""
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        """Intenta extreure una coordenada numèrica vàlida d'un string brut."""
        if raw is None or (isinstance(raw, float) and math.isnan(raw)): return None
        s = str(raw).strip().replace('−', '-') # Ull amb el guió menys diferent
        digits = re.sub(r"[^0-9-]", "", s)
        try:
            val_int = int(digits)
            # Heurística: dividim per potències de 10 fins a trobar una coord GPS raonable per BCN
            target, v_range = (41.5, (39.0, 44.0)) if is_lat else (2.0, (-1.0, 5.0))
            divisors = [10**i for i in range(10)]
            candidates = [val_int / d for d in divisors]
            hits = [c for c in candidates if v_range[0] <= c <= v_range[1]]
            return float(min(hits, key=lambda x: abs(x - target))) if hits else None
        except: return None

    """
    ############################################################################################
    ############################################################################################

    Mètodes Estàtics (Interfície Pública per Agents)
    S'utilitzen per comunicació ràpida entre Trens sense passar per la instància global.

    ############################################################################################
    ############################################################################################
    """

    @staticmethod
    def remove_train_from_edge(edge, train_id):
        """Elimina un tren de una vía específica (usado al cambiar de segmento)."""
        if edge and edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    @staticmethod
    def register_segment(u_name, v_name, edge_object):
        """Registra un segment físic al diccionari de cerca ràpida."""
        TrafficManager._physical_segments[(u_name, v_name)] = edge_object

    @staticmethod
    def get_edge(u_name, v_name):
        """Retorna l'objecte Edge que connecta u->v."""
        return TrafficManager._physical_segments.get((u_name, v_name))
    
    @staticmethod
    def check_alert(u_name, v_name, track_id):
        """Consulta si hi ha una incidència reportada en un segment."""
        return 1 if (u_name, v_name, track_id) in TrafficManager._reported_obstacles else 0
    
    @staticmethod
    def report_issue(u_name, v_name, track_id):
        """Un tren reporta una incidència (obstacle) al sistema central."""
        TrafficManager._reported_obstacles[(u_name, v_name, track_id)] = "ALERT"

    @staticmethod
    def update_train_position(edge, train_id, progress):
        """
        Actualitza la posició d'un tren dins d'una via (Edge).
        Utilitzat per gestionar cues i col·lisions.
        """
        if not edge: return
        if edge not in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = []
        
        # Eliminem entrada antiga i afegim la nova
        TrafficManager._train_positions[edge] = [
            (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
        ]
        TrafficManager._train_positions[edge].append((train_id, progress))
        
        # Ordenem per progrés (qui va primer)
        TrafficManager._train_positions[edge].sort(key=lambda x: x[1], reverse=True)

    @staticmethod
    def remove_train(train_id):
        """Elimina un tren de tots els registres de posició."""
        for edge in TrafficManager._train_positions:
            TrafficManager._train_positions[edge] = [
                (tid, p) for tid, p in TrafficManager._train_positions[edge] if tid != train_id
            ]

    @staticmethod
    def get_distance_to_leader(edge, my_train_id):
        """
        calcula distancia entre el tren actual i el de davant en la mateixa via.
        Retorna la distància en km. Si no hi ha ningú davant, retorna inf
        """
        if not edge or edge not in TrafficManager._train_positions:
            return float('inf')
        
        #llista de trens en aquesta via ordenada per progrés
        trains_on_edge = TrafficManager._train_positions[edge]
        
        my_idx = -1
        for i, (tid, prog) in enumerate(trains_on_edge):
            if tid == my_train_id:
                my_idx = i
                break
        
        #Si no estem a la llista o som el primer (índex 0), no hi ha ningú davant
        if my_idx <= 0:
            return float('inf')
            
        #El tren de davant és el que està a my_idx - 1
        leader_id, leader_prog = trains_on_edge[my_idx - 1]
        _, my_prog = trains_on_edge[my_idx]
        
        dist_km = (leader_prog - my_prog) * edge.real_length_km
        return dist_km

    # ==========================================
    # UTILITATS I DEBUG
    # ==========================================

    def save_brain(self):
        """Persisteix l'aprenentatge (Q-Table) a disc."""
        self.brain.save_table("Agent/Qtables/q_table.pkl")

    def debug_network_snapshot(self):
        """Imprimeix un resum de l'estat actual per consola."""
        print(f"\n=== SNAPSHOT XARXA (T={self.sim_time:.1f}) ===")
        print(f"Total Trens Actius: {len(self.active_trains)}")
        
        obstacles = len(self._reported_obstacles)
        if obstacles > 0:
            print(f" ALERTA: Hi ha {obstacles} segments amb incidències reportades!")

        print("--- LLISTA DE TRENS ---")
        for t in self.active_trains:
            delay = t.calculate_delay()
            seg = f"{t.node.name[:10]}->{t.target.name[:10]}" if t.target else "Fi Trayecte"
            print(f"{t.id % 1000:03d} | {seg:25} | v={t.current_speed:5.1f} | Delay: {delay:+5.1f}m")
        print("==========================================\n")