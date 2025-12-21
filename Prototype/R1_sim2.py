import pygame
import sys
import math
import random
import pandas as pd
import numpy as np
import pickle
import os
import re
import unicodedata
from enum import Enum
from typing import List, Dict, Tuple

# ==============================================================================
# 1. CLASSES BÀSIQUES DE L'ENTORN (NODES I ARESTES)
# ==============================================================================

class EdgeType(Enum):
    NORMAL = 1
    OBSTACLE = 2  # Avaria

class Node:
    def __init__(self, x, y, node_id, name=""):
        self.x = x
        self.y = y
        self.id = node_id
        self.name = name
        self.radius = 5
        self.highlight = False
        # Guardem els veïns per saber on podem anar: {id_veí: [edge_via_1, edge_via_2]}
        self.neighbors = {} 

    def draw(self, screen):
        color = (0, 100, 200) if not self.highlight else (255, 100, 0)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            text = font.render(self.name, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)

class Edge:
    def __init__(self, node1, node2, edge_type, duration, track_id):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.base_duration = duration
        self.track_id = track_id  # 0 o 1 (per identificar via paral·lela)
        self.update_properties()

    def update_properties(self):
        # Si està trencada, triga 5 vegades més
        factor = 1.0 if self.edge_type == EdgeType.NORMAL else 5.0
        self.current_duration = self.base_duration * factor
        # Velocitat de visualització (progrés per frame)
        self.speed = 1.0 / max(self.current_duration, 1)

    def draw(self, screen):
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        
        # Càlcul d'offset per dibuixar les dues vies paral·leles sense solapar-se
        off = 3 if self.track_id == 0 else -3
        
        # Vector direcció
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        
        # Vector perpendicular unitari (-dy, dx)
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Punts desplaçats
        start = (self.node1.x + perp_x * off, self.node1.y + perp_y * off)
        end = (self.node2.x + perp_x * off, self.node2.y + perp_y * off)
        
        pygame.draw.line(screen, color, start, end, width)

# ==============================================================================
# 2. L'AGENT INTEL·LIGENT (CERVELL)
# ==============================================================================

class QLearningAgent:
    def __init__(self, learning_rate=0.1, discount_factor=0.9, epsilon=0.1):
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = {} # Key: (node_origen, node_desti, estat_via_0, estat_via_1) -> Value: [Q_via0, Q_via1]

    def get_q_value(self, state, action):
        return self.q_table.get(state, [0.0, 0.0])[action]

    def choose_action(self, state):
        """Retorna 0 (Via 1) o 1 (Via 2)"""
        # Epsilon-greedy: Exploració vs Explotació
        if random.random() < self.epsilon:
            return random.choice([0, 1])
        
        q_values = self.q_table.get(state, [0.0, 0.0])
        # Si són iguals, tria a l'atzar, si no, el millor
        if q_values[0] == q_values[1]:
            return random.choice([0, 1])
        return np.argmax(q_values)

    def learn(self, state, action, reward, next_state):
        """Actualitza la Q-Table segons l'equació de Bellman"""
        current_q = self.get_q_value(state, action)
        
        # Max Q del següent estat (si fos una cadena de decisions)
        # En aquest cas simplificat, el següent estat és 'arribat', Q=0, però ho deixem preparat
        next_max_q = np.max(self.q_table.get(next_state, [0.0, 0.0]))
        
        new_q = current_q + self.lr * (reward + self.gamma * next_max_q - current_q)
        
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
        
        self.q_table[state][action] = new_q

# ==============================================================================
# 3. EL TREN (AGENT EN L'ENTORN)
# ==============================================================================

class Train:
    def __init__(self, agent, start_node, target_node, available_edges):
        self.agent = agent
        self.node = start_node
        self.target = target_node
        self.edges = available_edges # [Edge_via_0, Edge_via_1]
        
        self.current_edge = None
        self.progress = 0
        self.travel_time = 0
        self.finished = False
        self.state_at_departure = None
        self.action_taken = None

        # --- LÒGICA DE DECISIÓ (COMUNICACIÓ AMB AGENT) ---
        self.decide_route()

    def get_state(self):
        """Construeix l'estat que veu l'agent: On soc, on vaig, com estan les vies"""
        status_0 = "OK" if self.edges[0].edge_type == EdgeType.NORMAL else "BAD"
        status_1 = "OK" if self.edges[1].edge_type == EdgeType.NORMAL else "BAD"
        return (self.node.id, self.target.id, status_0, status_1)

    def decide_route(self):
        # 1. Preguntar a l'agent
        self.state_at_departure = self.get_state()
        self.action_taken = self.agent.choose_action(self.state_at_departure)
        
        # 2. Executar decisió
        self.current_edge = self.edges[self.action_taken]
        
        # Debug
        # print(f"Tren a {self.node.name}: Tria via {self.action_taken} ({self.state_at_departure[2]}/{self.state_at_departure[3]})")

    def update(self):
        if self.finished: return

        # Avançar
        self.progress += self.current_edge.speed
        self.travel_time += 1 # Comptem frames com a temps

        if self.progress >= 1.0:
            self.progress = 1.0
            self.finished = True
            
            # --- FEEDBACK A L'AGENT (RECOMPENSA) ---
            # La recompensa és negativa (cost temporal). Volem minimitzar temps.
            # Normalitzem una mica per no tenir valors gegants (ex: -100 punts)
            reward = -self.travel_time 
            
            # L'estat següent seria estar al node destí (sense moure's encara)
            next_state = (self.target.id, None, "None", "None") 
            
            self.agent.learn(self.state_at_departure, self.action_taken, reward, next_state)
            
            # print(f"Tren arribat! Reward: {reward:.1f}. Q-Table updated.")

    def draw(self, screen):
        if not self.current_edge: return
        
        # Calcular posició amb l'offset de la via
        off = 3 if self.current_edge.track_id == 0 else -3
        dx = self.current_edge.node2.x - self.current_edge.node1.x
        dy = self.current_edge.node2.y - self.current_edge.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Inici i final desplaçats
        x1 = self.current_edge.node1.x + perp_x * off
        y1 = self.current_edge.node1.y + perp_y * off
        x2 = self.current_edge.node2.x + perp_x * off
        y2 = self.current_edge.node2.y + perp_y * off
        
        curr_x = x1 + (x2 - x1) * self.progress
        curr_y = y1 + (y2 - y1) * self.progress
        
        pygame.draw.circle(screen, (255, 200, 0), (int(curr_x), int(curr_y)), 4)


# ==============================================================================
# 4. SIMULADOR PRINCIPAL (INTEGRACIÓ)
# ==============================================================================

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
        self.brain = QLearningAgent(epsilon=0.2) # 20% exploració

        # Timers
        self.last_chaos = pygame.time.get_ticks()
        self.last_reset = pygame.time.get_ticks()
        self.last_spawn = pygame.time.get_ticks()

        # Càrrega del mapa (versió resumida de la lògica anterior)
        self.load_map()

    def _normalize(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        return "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').upper()

    def load_map(self):
        # 1. Carregar CSV
        try:
            df = pd.read_csv('Enviroment/data/estaciones_coordenadas.csv', sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
            if 'NOMBRE_ESTACION' not in df.columns:
                df = pd.read_csv('Enviroment/data/estaciones_coordenadas.csv', sep=',', encoding='latin1')
                df.columns = [c.strip().upper() for c in df.columns]
        except: return

        # 2. Crear Nodes
        lats, lons, raw_nodes = [], [], []
        for _, row in df.iterrows():
            name = row.get('NOMBRE_ESTACION')
            if pd.isna(name): continue
            lat, lon = self._clean_coord(row.get('LATITUD')), self._clean_coord(row.get('LONGITUD'), False)
            if lat and lon:
                raw_nodes.append({'id': str(row.get('ID')), 'name': name, 'lat': lat, 'lon': lon, 'norm': self._normalize(name)})
                lats.append(lat); lons.append(lon)
        
        if not lats: return
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        pad_x, pad_y = (max_lon-min_lon)*0.05, (max_lat-min_lat)*0.05

        for d in raw_nodes:
            x = ((d['lon'] - (min_lon - pad_x)) / ((max_lon + pad_x) - (min_lon - pad_x))) * self.width
            y = self.height - ((d['lat'] - (min_lat - pad_y)) / ((max_lat + pad_y) - (min_lat - pad_y))) * self.height
            node = Node(x, y, d['id'], d['name'])
            node.lat, node.lon = d['lat'], d['lon']
            self.nodes[d['norm']] = node

        # 3. Connectar (Només exemple R1 per brevetat, afegeix la resta igual)
        r1 = [('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'), ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
             ('SANTJOANDESPI', 'CORNELLA'), ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
             ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'), ('BARCELONASANTS', 'PLACADECATALUNYA'),
             ('PLACADECATALUNYA', 'ARCDETRIOMF'), ('ARCDETRIOMF', 'BARCELONACLOTARAGO'),
             ('BARCELONACLOTARAGO', 'SANTADRIADEBESOS'), ('SANTADRIADEBESOS', 'BADALONA'),
             ('BADALONA', 'MONTGAT'), ('MONTGAT', 'MONTGATNORD'), ('MONTGATNORD', 'ELMASNOU'),
             ('ELMASNOU', 'OCATA'), ('OCATA', 'PREMIADEMAR'), ('PREMIADEMAR', 'VILASSARDEMAR'),
             ('VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR'), ('CABRERADEMARVILASSARDEMAR', 'MATARO')]
        
        for u, v in r1:
            self.add_double_track(u, v)

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