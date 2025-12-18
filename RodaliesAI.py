import pygame
import math
import random
import pandas as pd
import re
import unicodedata

#__________________________________________________________
import Enviroment.EdgeType as EdgeType
import Enviroment.Edge as Edge
#__________________________________________________________

import Enviroment.Train as Train
import Enviroment.Node as Node
import Agent.QlearningAgent as QLearningAgent


class RodaliesAI:
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies AI - Q-Learning Train Control")
        self.clock = pygame.time.Clock()
        self.running = True

        # Dades
        self.nodes = {}
        self.all_edges = []
        self.active_trains = []
        
        # AI
        self.brain = QLearningAgent.QLearningAgent(epsilon=0.2) # 20% exploració

        # Timers
        self.last_chaos = pygame.time.get_ticks()
        self.last_reset = pygame.time.get_ticks()
        self.last_spawn = pygame.time.get_ticks()

        # Càrrega del mapa (versió resumida de la lògica anterior)
        self.load_real_data()

    def _normalize(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        return "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').upper()

    def load_real_data(self):
        # 1. Llegir CSV amb gestió d'espais
        csv_path = 'data/estaciones_coordenadas.csv'
        try:
            # skipinitialspace=True ajuda si hi ha espais després del punt i coma
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            
            # NETEJA CRÍTICA: Eliminem espais en blanc dels noms de les columnes i ho passem a majúscules
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Comprovació de seguretat
            if 'NOMBRE_ESTACION' not in df.columns:
                print(f"Alerta: Columnes trobades: {df.columns}")
                # Intent alternatiu amb coma
                df = pd.read_csv(csv_path, sep=',', encoding='latin1')
                df.columns = [c.strip().upper() for c in df.columns]

        except Exception as e:
            print(f"Error llegint CSV: {e}")
            return

        # 2. Processar Estacions
        temp_stations = []
        lats, lons = [], []

        for _, row in df.iterrows():
            # Ara accedim segurs perquè hem netejat les columnes
            name = row.get('NOMBRE_ESTACION')
            
            # Si encara falla, intentem buscar manualment la columna que contingui 'ESTACION'
            if pd.isna(name):
                col_name = next((c for c in df.columns if 'ESTACION' in c), None)
                if col_name:
                    name = row[col_name]
            
            if pd.isna(name): 
                continue
            
            norm_name = self._normalize_name(name)
            lat = self._parse_coord(row.get('LATITUD'), is_lat=True)
            lon = self._parse_coord(row.get('LONGITUD'), is_lat=False)
            
            if lat and lon:
                temp_stations.append({
                    'id': str(row.get('ID', '')), 
                    'norm': norm_name, 
                    'orig': name, # El nom original
                    'lat': lat, 
                    'lon': lon
                })
                lats.append(lat)
                lons.append(lon)

        if not lats: 
            print("No s'han trobat coordenades vàlides.")
            return

        # Calcular Bounding Box per escalar el mapa a la pantalla
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Padding del 5% perquè no quedin enganxats a la vora
        lat_pad = (max_lat - min_lat) * 0.05
        lon_pad = (max_lon - min_lon) * 0.05
        min_lat -= lat_pad; max_lat += lat_pad
        min_lon -= lon_pad; max_lon += lon_pad

        # 3. Crear Nodes
        for st in temp_stations:
            # Projecció simple a pantalla
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * self.width
            y = self.height - ((st['lat'] - min_lat) / (max_lat - min_lat)) * self.height
            
            node = Node(x, y, st['id'])
            
            # ASSIGNACIÓ CLAU: Assignem 'name' perquè la classe Node del simulator.py el pugui dibuixar
            node.name = st['orig']  
            
            # Guardem lat/lon reals per si calgués
            node.lat = st['lat']
            node.lon = st['lon']
            
            self.nodes[st['norm']] = node
            
        #self.build_lines()
        self.build_R1()

    def build_R1(self):
        # Definició de línies (com al codi anterior)
        lines = [
            # R1
            [('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'), ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
             ('SANTJOANDESPI', 'CORNELLA'), ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
             ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'), ('BARCELONASANTS', 'PLACADECATALUNYA'),
             ('PLACADECATALUNYA', 'ARCDETRIOMF'), ('ARCDETRIOMF', 'BARCELONACLOTARAGO'),
             ('BARCELONACLOTARAGO', 'SANTADRIADEBESOS'), ('SANTADRIADEBESOS', 'BADALONA'),
             ('BADALONA', 'MONTGAT'), ('MONTGAT', 'MONTGATNORD'), ('MONTGATNORD', 'ELMASNOU'),
             ('ELMASNOU', 'OCATA'), ('OCATA', 'PREMIADEMAR'), ('PREMIADEMAR', 'VILASSARDEMAR'),
             ('VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR'), ('CABRERADEMARVILASSARDEMAR', 'MATARO'),
             ('MATARO', 'SANTANDREUDELLAVANERES'), ('SANTANDREUDELLAVANERES', 'CALDESDESTRAC'),
             ('CALDESDESTRAC', 'ARENYSDEMAR'), ('ARENYSDEMAR', 'CANETDEMAR'),
             ('CANETDEMAR', 'SANTPOLDEMAR'), ('SANTPOLDEMAR', 'CALELLA'),
             ('CALELLA', 'PINEDADEMAR'), ('PINEDADEMAR', 'SANTASUSANNA'),
             ('SANTASUSANNA', 'MALGRATDEMAR'), ('MALGRATDEMAR', 'BLANES'),
             ('BLANES', 'TORDERA'), ('TORDERA', 'MACANETMASSANES')]
        ]

        for line in lines:
            for s1, s2 in line:
                self.add_connection(s1, s2)

    def _clean_coord(self, raw, is_lat=True):
        # Neteja ràpida
        try:
            s = str(raw).strip().replace(',', '.')
            val = float(re.sub(r"[^0-9\.-]", "", s))
            while abs(val) > 180: val /= 10 # Reduir magnituds boges
            return val
        except: return None

    def add_double_track(self, name1, name2):
        n1, n2 = self._normalize(name1), self._normalize(name2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            
            # Distància i temps
            dist = math.sqrt((u.x-v.x)**2 + (u.y-v.y)**2) # Pixels com a mètrica simple
            duration = dist * 0.5 # Factor arbitratrio
            
            # Creem 2 vies d'anada (0 i 1)
            e0 = Edge(u, v, EdgeType.NORMAL, duration, 0)
            e1 = Edge(u, v, EdgeType.NORMAL, duration, 1)
            self.all_edges.extend([e0, e1])
            
            # Guardem al node perquè sàpiga com anar al veí
            if v.id not in u.neighbors: u.neighbors[v.id] = []
            u.neighbors[v.id] = [e0, e1] # [Via0, Via1]
            
            # (Opcional: fer el mateix en sentit contrari v->u)

    def handle_mechanics(self):
        now = pygame.time.get_ticks()
        
        # 1. Reset (20s)
        if now - self.last_reset > 20000:
            self.last_reset = now
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
        
        # 2. Caos (5s)
        elif now - self.last_chaos > 5000:
            self.last_chaos = now
            # Arreglar un
            broken = [e for e in self.all_edges if e.edge_type == EdgeType.OBSTACLE]
            if broken:
                e = random.choice(broken)
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
            # Trencar dos
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()

        # 3. Generar Trens (Cada 0.5s per accelerar aprenentatge)
        if now - self.last_spawn > 500:
            self.last_spawn = now
            self.spawn_random_train()

    def spawn_random_train(self):
        # Triar un node d'origen que tingui veïns
        origins = [n for n in self.nodes.values() if n.neighbors]
        if not origins: return
        
        start = random.choice(origins)
        # Triar un veí destí
        target_id = random.choice(list(start.neighbors.keys()))
        target = next(n for n in self.nodes.values() if n.id == target_id)
        
        available_edges = start.neighbors[target_id] # [Via0, Via1]
        
        # Crear tren i assignar-lo al cervell
        new_train = Train(self.brain, start, target, available_edges)
        self.active_trains.append(new_train)

    def draw(self):
        self.screen.fill((240, 240, 240))
        for e in self.all_edges: e.draw(self.screen)
        for n in self.nodes.values(): n.draw(self.screen)
        for t in self.active_trains: t.draw(self.screen)
        
        # UI
        font = pygame.font.SysFont("Arial", 16)
        info = font.render(f"Trens Actius: {len(self.active_trains)} | Epsilon: {self.brain.epsilon:.2f}", True, (0,0,0))
        self.screen.blit(info, (10, 10))
        
        # Estadístiques Q-Table (Breu)
        q_info = f"Estats apresos: {len(self.brain.q_table)}"
        self.screen.blit(font.render(q_info, True, (0,0,0)), (10, 30))

        pygame.display.flip()

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.running = False

            self.handle_mechanics()
            
            # Actualitzar trens i netejar els acabats
            for t in self.active_trains: t.update()
            self.active_trains = [t for t in self.active_trains if not t.finished]
            
            self.draw()
            self.clock.tick(60)
        pygame.quit()

if __name__ == "__main__":
    sim = RodaliesAI()
    sim.run()