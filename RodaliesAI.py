import pygame
import random
import pandas as pd
import math
import re
import unicodedata
import os
import json
import pickle
from collections import defaultdict
from geopy.distance import great_circle

# --- IMPORTS DEL PROJECTE ---
from Enviroment.EdgeType import EdgeType
from Enviroment.Edge import Edge
from Enviroment.Node import Node
from Enviroment.Train import Train
from Enviroment.TrafficManager import TrafficManager
from Enviroment.Datas import Datas
import Agent.QlearningAgent as QLearningAgent


class RodaliesAI:
    """
    CLASSE PRINCIPAL DE VISUALITZACIÓ (PYGAME)
    """
    # --- CONFIGURACIÓ DEL SISTEMA DE TEMPS ---
    TIME_SCALE = 10.0      # 1 segon real = 10 minuts simulats
    SPAWN_INTERVAL = 30    # Cada quants minuts simulats surt un tren
    RESET_INTERVAL = 210   # Cada quants minuts es reseteja la via (3.5h)
    CHAOS_INTERVAL = 60    # Cada quants minuts hi ha incidents (1h)
    
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
        
        # Cervell "Global" per carregar/guardar (encara que cada tren té el seu)
        self.brain = QLearningAgent.QLearningAgent(epsilon=0.2)
        self.brain.load_table("q_table.pkl")

        # --- SISTEMA DE TEMPS UNIFICAT ---
        self.sim_time = 0.0
        self.last_chaos = self.sim_time
        self.last_reset = self.sim_time
        self.last_spawn = self.sim_time

        self.load_real_data()

    # ... (MÈTODES DE CÀRREGA DE DADES I MAPA - IGUAL QUE ABANS) ...
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
            # Passem self.brain (o carrega pròpia)
            new_train = Train(train_id=len(self.active_trains), start_delay=self.sim_time)
            # Assignar ruta manualment perquè Train per defecte usa R1_ROUTES de Datas
            new_train.route = [] # (Opcional: adaptar Train per acceptar rutes custom)
            # En la simulació visual, el Train pot necessitar ajustos. 
            # Per simplificar, assumim que Train usa la lògica per defecte o l'assignem aquí:
            # new_train.node = route_nodes[0] ...
            # *NOTA*: El constructor de Train a la classe enviada per l'usuari era bàsic.
            # Aquí mantenim la lògica original del run() visual.
            self.active_trains.append(new_train)

    def spawn_random_train(self):
        # Simplificat per fer servir els constructors per defecte que funcionen amb Datas
        t_id = len(self.active_trains)
        # Train s'inicialitza amb ruta automàtica segons ID a la classe Train
        new_train = Train(t_id, start_delay=self.sim_time)
        self.active_trains.append(new_train)

    def handle_mechanics(self):
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
            TrafficManager.reset()
            print(f"Dia nou: Vies i Incidències netejades al minut {int(self.sim_time)}")
        
        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            if len(normals) > 2:
                for e in random.sample(normals, 2):
                    e.edge_type = EdgeType.OBSTACLE
                    e.update_properties()

    def run(self):
        print("--- INICIANT MODE SIMULACIÓ VISUAL ---")
        try:
            while self.running:
                dt_ms = self.clock.tick(60)       
                dt_real_seconds = dt_ms / 1000.0          
                dt_sim_minutes = dt_real_seconds * self.TIME_SCALE 
                self.sim_time += dt_sim_minutes

                for event in pygame.event.get():
                    if event.type == pygame.QUIT: self.running = False
                
                self.handle_mechanics()
                
                # Spawner simple
                if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
                    self.last_spawn = self.sim_time
                    if len(self.active_trains) < 10:
                        self.spawn_random_train()

                for t in self.active_trains: t.update(dt_sim_minutes)
                self.active_trains = [t for t in self.active_trains if not t.finished]

                self.screen.fill((240, 240, 240))
                for e in self.all_edges: e.draw(self.screen)
                for n in self.nodes.values(): n.draw(self.screen)
                for t in self.active_trains: t.draw(self.screen)
                
                debug_font = pygame.font.SysFont("Arial", 16)
                days = int(self.sim_time // 1440)
                hours = int((self.sim_time % 1440) // 60)
                mins = int(self.sim_time % 60)
                
                time_str = f"Dia {days} | {hours:02d}:{mins:02d}"
                msg = debug_font.render(f"{time_str} | Trens: {len(self.active_trains)} | Scale: x{self.TIME_SCALE}", True, (0,0,0))
                self.screen.blit(msg, (10, 10))

                pygame.display.flip()
            
        except Exception as e:
            print(f"Error inesperat durant l'execució: {e}")
        finally:
            self.brain.save_table("q_table.pkl")
            pygame.quit()
            print("Simulació finalitzada i dades guardades.")


############################################################################################
############################################################################################
#
#   CLASSE D'ENTORN MULTI-AGENT (MODE ENTRENAMENT - CONSOLE)
#
############################################################################################
############################################################################################

class MultiAgentR1Environment:
    """
    Entorn lògic (sense gràfics) per entrenar ràpidament.
    """
    def __init__(self, num_trains=2, train_spacing=8, p_inc=0.015, routes=None, siding_stations=None):
        self.num_trains = num_trains
        self.train_spacing = train_spacing
        self.p_inc = p_inc
        self.trains = []
        self.occupied_segments = {}
        self.siding_stations = set(siding_stations) if siding_stations else Datas.R1_SIDING_STA
        
        for i in range(num_trains):
            route_idx = routes[i] if routes and i < len(routes) else None
            train = Train(train_id=i, start_delay=i * train_spacing, route_idx=route_idx)
            self.trains.append(train)

    @property
    def agents(self):
        return [t.agent for t in self.trains]

    def reset(self):
        self.occupied_segments.clear()
        for i, train in enumerate(self.trains):
            train.reset(start_delay=i * self.train_spacing)
        return self.get_states()

    def get_state(self, train):
        if train.done or train.idx >= len(train.route) - 1: return None
        segment = train.current_segment()
        if segment is None: return None

        origen, destino = segment
        diff = train.real_time - train.scheduled_time
        diff_disc = train.agent.discretize_diff(diff)
        is_blocked = 1 if segment in self.occupied_segments and self.occupied_segments[segment] != train.train_id else 0
        return (origen, destino, diff_disc, is_blocked)

    def get_states(self):
        return [self.get_state(train) for train in self.trains]

    def step(self, actions):
        rewards = [0.0] * self.num_trains
        self.occupied_segments.clear()
        
        # 1. Determinar ocupació
        for i, train in enumerate(self.trains):
            if not train.done:
                seg = train.current_segment()
                if seg:
                    origen, _ = seg
                    diff_here = train.real_time - train.scheduled_time
                    # Acció 3 = APARTAR
                    if not (actions[i] == 3 and origen in self.siding_stations and diff_here <= 0):
                        self.occupied_segments[seg] = train.train_id

        # 2. Executar accions
        for i, (train, action) in enumerate(zip(self.trains, actions)):
            if train.done: continue
            
            segment = train.current_segment()
            if not segment:
                train.done = True
                continue

            origen, destino = segment
            base_time = Datas.R1_TIME.get(segment, 3)
            diff = train.real_time - train.scheduled_time
            is_blocked = segment in self.occupied_segments and self.occupied_segments[segment] != train.train_id

            # -- Logica APARTAR --
            if action == 3:
                if origen in self.siding_stations:
                    if diff <= 0: # Anem bé de temps, podem deixar passar
                        # Check benefici
                        beneficioso = False
                        for j, other in enumerate(self.trains):
                            if j == i or other.done: continue
                            if other.current_segment() == segment:
                                if (other.real_time - other.scheduled_time) > 1 and actions[j] != 3:
                                    beneficioso = True
                                    break
                        train.waiting_at_station = True
                        train.wait_time += 1
                        rewards[i] += 20 if beneficioso else -5
                        continue
                    else:
                        # Retardat i apartant-se = malament
                        train.waiting_at_station = True
                        train.wait_time += 1
                        rewards[i] -= 10
                        continue
                else:
                    # No es pot apartar
                    train.waiting_at_station = True
                    train.wait_time += 1
                    rewards[i] -= 10
                    continue

            # -- Logica MOVIMENT --
            elif is_blocked:
                train.waiting_at_station = True
                train.wait_time += 1
                rewards[i] -= 50
                continue
            else:
                train.waiting_at_station = False
                if action == 0: delta = -1   # Accel
                elif action == 2: delta = 1  # Frena
                else: delta = 0              # Manté

                travel_time = max(1, base_time + delta)

            # Incidències
            if random.random() < self.p_inc:
                travel_time += random.randint(3, 10)

            train.real_time += travel_time + Datas.STOP_STA_TIME
            train.scheduled_time += base_time + Datas.STOP_STA_TIME
            train.idx += 1

            # Reward per puntualitat
            new_diff = train.real_time - train.scheduled_time
            if new_diff == 0: rewards[i] = 100
            else: rewards[i] = -abs(new_diff) - 50

            if train.idx >= len(train.route) - 1:
                train.done = True

        return self.get_states(), rewards, all(t.done for t in self.trains)


# --- FUNCIONS AUXILIARS D'ENTRENAMENT ---

def train_console_mode():
    print("\n" + "="*50)
    print("CONFIGURACIÓ DE L'ENTRENAMENT")
    print("="*50)
    try:
        episodes = int(input("Nombre d'episodis [Defecte 5000]: ") or "5000")
        num_trains = int(input("Nombre de trens [Defecte 4]: ") or "4")
    except ValueError:
        print("Valors invàlids. Usant defectes.")
        episodes = 5000
        num_trains = 4
    
    print(f"\nIniciant entrenament: {num_trains} trens, {episodes} episodis...")
    
    env = MultiAgentR1Environment(num_trains=num_trains, train_spacing=10)
    
    # Parametres inicials
    for a in env.agents:
        a.epsilon = 0.2
        a.alpha = 0.1

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    history_rewards = []
    
    for ep in range(episodes):
        # Alpha/Epsilon Decay
        curr_alpha = 0.1 * (0.98 ** (ep / 100))
        epsilon_decay = 0.99 ** (ep / 50)
        
        for a in env.agents:
            a.alpha = curr_alpha
            a.epsilon = max(0.01, 0.2 * epsilon_decay)

        states = env.reset()
        total_reward = 0
        
        while not all(t.done for t in env.trains):
            actions = []
            for i, (agent, state) in enumerate(zip(env.agents, states)):
                if state is None or env.trains[i].done:
                    actions.append(1)
                else:
                    actions.append(agent.action(state))
            
            next_states, rewards, _ = env.step(actions)
            
            for i, agent in enumerate(env.agents):
                if states[i] is not None and not env.trains[i].done:
                    agent.update(states[i], actions[i], rewards[i], next_states[i])
            
            states = next_states
            total_reward += sum(rewards)
        
        history_rewards.append(total_reward)
        
        if ep % 200 == 0:
            print(f"Episodi {ep} | Reward Total: {total_reward:.1f} | Epsilon: {env.agents[0].epsilon:.3f}")

    print("\nEntrenament completat.")
    
    # Guardar resultats
    os.makedirs("multiAgentData", exist_ok=True)
    
    # 1. Guardar Q-Tables
    for i, agent in enumerate(env.agents):
        agent.save_table(f"multiAgentData/agent_{i}.pkl")
    
    # 2. Gràfica
    plt.figure(figsize=(10,5))
    plt.plot(history_rewards)
    plt.title("Evolució del Reward (Training)")
    plt.savefig("multiAgentData/training_plot.png")
    print("Gràfica guardada a 'multiAgentData/training_plot.png'")
    print("Taules guardades a 'multiAgentData/'")
    print("Pots tancar o tornar a executar per veure la simulació visual amb les noves taules.")


############################################################################################
############################################################################################
#
#   MAIN / SELECTOR
#
############################################################################################
############################################################################################

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("       RODALIES AI - SYSTEM SELECTOR")
    print("#"*60)
    print("1. SIMULACIÓ VISUAL (Pygame)")
    print("   -> Veure els trens moure's en el mapa.")
    print("2. ENTRENAMENT MULTI-AGENT (Consola)")
    print("   -> Entrenar la lògica a màxima velocitat.")
    print("#"*60)
    
    opcio = input("\nSelecciona una opció (1 o 2): ").strip()
    
    if opcio == "2":
        train_console_mode()
    else:
        # Per defecte arrenca la visual
        app = RodaliesAI()
        app.run()