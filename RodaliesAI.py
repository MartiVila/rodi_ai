import pygame
import random
import pandas as pd
import math
import re
import unicodedata
from geopy.distance import great_circle

# Delegació total a Enviroment i Agent
from Enviroment.EdgeType import EdgeType
from Enviroment.Edge import Edge
from Enviroment.Node import Node
from Enviroment.Train import Train
import Agent.QlearningAgent as QLearningAgent

class RodaliesAI:
    # --- CONFIGURACIÓ DEL SISTEMA DE TEMPS ---
    TIME_SCALE = 10.0      # 1 segon real = 10 minuts simulats
    SPAWN_INTERVAL = 30    # Cada quants minuts simulats surt un tren

    #RESET_INTERVAL = 1440  # Cada quants minuts es reseteja la via (24h)
    #CHAOS_INTERVAL = 600   # Cada quants minuts hi ha incidents (10h)

    RESET_INTERVAL = 210  # Cada quants minuts es reseteja la via (3.5h)
    CHAOS_INTERVAL = 60   # Cada quants minuts hi ha incidents (1h)
    
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        #self.screen = pygame.display.toggle_fullscreen()
        pygame.display.set_caption("Rodalies AI - Q-Learning Train Control")
        self.clock = pygame.time.Clock()
        self.running = True

        # Estructures de dades
        self.nodes = {}
        self.all_edges = []
        self.active_trains = []
        
        # Agent
        self.brain = QLearningAgent.QLearningAgent(epsilon=0.2) 

        # --- SISTEMA DE TEMPS UNIFICAT ---
        # Tot s'inicialitza a 0.0 (minuts de simulació)
        self.sim_time = 0.0
        
        # Timers sincronitzats amb el temps de simulació, no amb el de la CPU
        self.last_chaos = self.sim_time
        self.last_reset = self.sim_time
        self.last_spawn = self.sim_time

        self.load_real_data()

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

    def load_real_data(self):
        self.r1_connections = [
            ('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'), ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
            ('SANTJOANDESPI', 'CORNELLA'), ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
            ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'), ('BARCELONASANTS', 'PLACADECATALUNYA'),
            ('PLACADECATALUNYA', 'ARCDETRIOMF'), ('ARCDETRIOMF', 'BARCELONACLOTARAGO')
        ]

        wanted_stations = set()
        for s1, s2 in self.r1_connections:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception: return

        lats, lons, temp_st = [], [], []
        for _, row in df.iterrows():
            name = row.get('NOMBRE_ESTACION')
            norm_name = self._normalize_name(name)
            if norm_name not in wanted_stations: continue 

            lat, lon = self._parse_coord(row.get('LATITUD'), True), self._parse_coord(row.get('LONGITUD'), False)
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

        self.build_R1()

    def add_connection(self, s1, s2):
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            if hasattr(u, 'lat') and u.lat and hasattr(v, 'lat') and v.lat:
                dist = great_circle((u.lat, u.lon), (v.lat, v.lon)).km
            else:
                dist = math.sqrt((u.x-v.x)**2 + (u.y-v.y)**2) * 0.05 
            
            e0 = Edge(u, v, EdgeType.NORMAL, 0)
            e1 = Edge(u, v, EdgeType.NORMAL, 1)
            self.all_edges.extend([e0, e1])
            u.neighbors[v.id] = [e0, e1]

    def build_R1(self):
        for s1, s2 in self.r1_connections: 
            self.add_connection(s1, s2)
        self.lines = {}
        self.lines['R1_NORD'] = [
            'MOLINSDEREI', 'SANTFELIUDELLOBREGAT', 'SANTJOANDESPI', 'CORNELLA', 
            'LHOSPITALETDELLOBREGAT', 'BARCELONASANTS', 'PLACADECATALUNYA', 
            'ARCDETRIOMF', 'BARCELONACLOTARAGO'
        ]
        self.lines['R1_SUD'] = self.lines['R1_NORD'][::-1]



    def calculate_schedule(self, route_nodes, start_time):
        """
        Cada cop que un tren es crea, es calcula el seu horari basat en els nodes de la ruta i el temps d'inici.
        Aquest horari es guarda en un diccionari on les claus son els IDs dels nodes i els valors son els temps d'arribada previstos.
        
        :param route_nodes: Llista de nodes que componen la ruta del tren.
        :param start_time: Temps d'inici del tren en minuts de simulació.   
        """ 
        schedule = {}
        current_time = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        for i in range(len(route_nodes) - 1):
            u, v = route_nodes[i], route_nodes[i+1]
            if v.id in u.neighbors:
                edges = u.neighbors[v.id]
                travel_time = edges[0].expected_minutes
                current_time += travel_time
                schedule[v.id] = current_time
            else: break
        return schedule

    def spawn_line_train(self, line_name):
        if line_name not in self.lines: return
        station_names = self.lines[line_name]
        route_nodes = [self.nodes[n] for n in station_names if n in self.nodes]
        
        if len(route_nodes) > 1:
            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            new_train = Train(self.brain, route_nodes, schedule, self.sim_time)
            self.active_trains.append(new_train)

    def spawn_random_train(self):
        origins = [n for n in self.nodes.values() if n.neighbors]
        if not origins: return
        start = random.choice(origins)
        target_id = random.choice(list(start.neighbors.keys()))
        target = next(n for n in self.nodes.values() if n.id == target_id)
        
        route_nodes = [start, target]
        schedule = self.calculate_schedule(route_nodes, self.sim_time)
        self.active_trains.append(Train(self.brain, route_nodes, schedule, self.sim_time))

    def handle_mechanics(self):
        """
        Gestiona esdeveniments basats en el temps de simulació.
        És a dir, els elements pseudoperiodics com el reset diari de la via i la introducció d'obstacles aleatoris.
        """
        # Reset diari (neteja d'obstacles)
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
        
        # Caos aleatori (obstacles)
        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()

    def run(self):
        while self.running:
            # 1. Càlcul del temps unificat
            dt_ms = self.clock.tick(60)       
            dt_real_seconds = dt_ms / 1000.0          
            dt_sim_minutes = dt_real_seconds * self.TIME_SCALE 
            
            self.sim_time += dt_sim_minutes

            # 2. Events Input
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
            
            # 3. Lògica del Món
            self.handle_mechanics()
            
            # 4. Spawner
            if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
                self.last_spawn = self.sim_time
                if random.random() < 0.8:
                    self.spawn_line_train('R1_NORD')
                else:
                    self.spawn_random_train()

            # 5. Actualització Trens
            for t in self.active_trains: t.update(dt_sim_minutes)
            self.active_trains = [t for t in self.active_trains if not t.finished]

            # 6. Dibuix
            self.screen.fill((240, 240, 240))
            for e in self.all_edges: e.draw(self.screen)
            for n in self.nodes.values(): n.draw(self.screen)
            for t in self.active_trains: t.draw(self.screen)
            
            # HUD Debug
            debug_font = pygame.font.SysFont("Arial", 16)
            # Format: Dies : Hores : Minuts
            days = int(self.sim_time // 1440)
            hours = int((self.sim_time % 1440) // 60)
            mins = int(self.sim_time % 60)
            
            time_str = f"Dia {days} | {hours:02d}:{mins:02d}"
            msg = debug_font.render(f"{time_str} | Trens: {len(self.active_trains)} | Scale: x{self.TIME_SCALE}", True, (0,0,0))
            self.screen.blit(msg, (10, 10))

            pygame.display.flip()
            
        pygame.quit()

if __name__ == "__main__":
    RodaliesAI().run()