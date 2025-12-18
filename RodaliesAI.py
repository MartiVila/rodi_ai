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
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies AI - Q-Learning Train Control")
        self.clock = pygame.time.Clock()
        self.running = True

        # Estructures de dades
        self.nodes = {}
        self.all_edges = []
        self.active_trains = []
        
        # L'agent es troba al lloc correcte: s'inicialitza un cop i es passa als trens
        self.brain = QLearningAgent.QLearningAgent(epsilon=0.2) 

        # Timers per a la mecànica de simulació
        self.last_chaos = pygame.time.get_ticks()
        self.last_reset = pygame.time.get_ticks()
        self.last_spawn = pygame.time.get_ticks()

        self.load_real_data()

    def _normalize_name(self, name):
        """Utilitza la mateixa lògica de normalització que el prototip."""
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        """Implementa la neteja de coordenades del prototip."""
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

            if norm_name not in wanted_stations:
                continue 

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
        """Crea connexions delegant la lògica de l'aresta a Enviroment."""
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            if u.lat is not None and u.lon is not None and v.lat is not None and v.lon is not None:
                dist = great_circle((u.lat, u.lon), (v.lat, v.lon)).km
            else:
                dist = math.sqrt((u.x-v.x)**2 + (u.y-v.y)**2) 
            #el factor de multiplicacio de dist es pel temps que volem que fagi el tren 1 km
            e0, e1 = Edge(u, v, EdgeType.NORMAL, dist * 50, 0), Edge(u, v, EdgeType.NORMAL, dist * 50, 1) #
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

    def spawn_line_train(self, line_name):
        """Genera un tren que recorrerà tota la línia especificada."""
        if line_name not in self.lines: return

        # Convertim noms d'estacions a objectes Node
        station_names = self.lines[line_name]
        route_nodes = []
        for name in station_names:
            if name in self.nodes:
                route_nodes.append(self.nodes[name])
        
        # Només creem el tren si la ruta és vàlida i té almenys 2 estacions
        if len(route_nodes) > 1:
            # Passem la llista completa de nodes al tren
            new_train = Train(self.brain, route_nodes)
            self.active_trains.append(new_train)

    def handle_mechanics(self):
        """Actualitza l'estat de les arestes delegant a la seva pròpia gestió interna."""
        now = pygame.time.get_ticks()
        if now - self.last_reset > 12000:
            self.last_reset = now
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties() # Delega el recàlcul de velocitat
        elif now - self.last_chaos > 5000:
            self.last_chaos = now
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()

    def spawn_random_train(self):
        """Delega la decisió de ruta a la classe Train, que usa l'agent."""
        origins = [n for n in self.nodes.values() if n.neighbors]
        if not origins: return
        start = random.choice(origins)
        target_id = random.choice(list(start.neighbors.keys()))
        target = next(n for n in self.nodes.values() if n.id == target_id)
        # El tren rep l'agent i pren la seva pròpia decisió al néixer
        self.active_trains.append(Train(self.brain, start, target, start.neighbors[target_id]))

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False
            
            self.handle_mechanics()
            for t in self.active_trains: t.update() # El tren mou, aprèn i es tanca sol
            self.active_trains = [t for t in self.active_trains if not t.finished]
            
            if pygame.time.get_ticks() - self.last_spawn > 500:
                self.last_spawn = pygame.time.get_ticks()
                #self.spawn_random_train()
                #self.spawn_origin_train()
                self.spawn_line_train('R1_NORD')

            # Dibuix delegat
            self.screen.fill((240, 240, 240))
            for e in self.all_edges: e.draw(self.screen) #
            for n in self.nodes.values(): n.draw(self.screen) #
            for t in self.active_trains: t.draw(self.screen) #
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()

if __name__ == "__main__":
    RodaliesAI().run()