import pygame
import random
import pandas as pd
import math
import re
import unicodedata
import os
from geopy.distance import great_circle

# [MODIFICACIÓ] Imports actualitzats per fer servir la nova arquitectura
from Enviroment.Datas import Datas
from Enviroment.EdgeType import EdgeType
from Enviroment.Edge import Edge
from Enviroment.Node import Node
from Enviroment.Train import Train 
import Agent.QlearningAgent as QLearningAgent
from Enviroment.TrafficManager import TrafficManager

# [NOU] Funció global per normalitzar noms i casar Datas.py amb el CSV
def normalize_name(name):
    if not isinstance(name, str): return ""
    n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
    n = n.replace('ñ', 'n').replace('ç', 'c')
    n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
    return n.upper()

# [NOU] Pre-càlcul de temps normalitzats per a accés ràpid durant l'entrenament
NORMALIZED_TIMES = {}
for (orig, dest), t in Datas.R1_TIME.items():
    n_orig = normalize_name(orig)
    n_dest = normalize_name(dest)
    NORMALIZED_TIMES[(n_orig, n_dest)] = t
    NORMALIZED_TIMES[(n_dest, n_orig)] = t 

# ==========================================================================================
# [NOU] CLASSE D'ENTORN MULTI-AGENT (LÒGICA PURA PER ENTRENAMENT)
# ==========================================================================================
class MultiAgentR1Environment:
    """
    Entorn simulat per entrenar N trens simultàniament sense interfície gràfica.
    Utilitza la mateixa classe Train i Datas.py.
    """
    def __init__(self, num_trains=2, train_spacing=8, p_inc=0.015):
        self.num_trains = num_trains
        self.train_spacing = train_spacing
        self.p_inc = p_inc
        self.trains = []
        # Normalitzem estacions amb apartador
        self.siding_stations = {normalize_name(s) for s in Datas.R1_SIDING_STA}
        self.occupied_segments = {} 
        
        for i in range(num_trains):
            # Usem la teva classe Train. Ella mateixa crea el seu agent internament.
            t = Train(train_id=i, start_delay=i * train_spacing)
            self.trains.append(t)

    def reset(self):
        self.occupied_segments.clear()
        states = []
        for i, train in enumerate(self.trains):
            train.reset(start_delay=i * self.train_spacing)
            states.append(self.get_state(train))
        return states

    def get_state(self, train):
        if train.done or train.idx >= len(train.route) - 1: return None
        seg = train.current_segment()
        if seg is None: return None
        
        n_orig, n_dest = normalize_name(seg[0]), normalize_name(seg[1])
        diff = train.real_time - train.scheduled_time
        
        # Usem l'agent per discretitzar (si té la funció, sino fallback)
        diff_disc = train.agent.discretize_diff(diff) if hasattr(train.agent, 'discretize_diff') else diff
        
        key = (n_orig, n_dest)
        is_blocked = 1 if key in self.occupied_segments and self.occupied_segments[key] != train.train_id else 0
        
        return (n_orig, n_dest, diff_disc, is_blocked)

    def step(self, actions):
        rewards = [0.0] * self.num_trains
        self.occupied_segments.clear()
        
        # 1. Bloqueig de vies
        for i, train in enumerate(self.trains):
            if not train.done:
                seg = train.current_segment()
                if seg and actions[i] != 3: # Si no s'aparta, ocupa
                    n_o, n_d = normalize_name(seg[0]), normalize_name(seg[1])
                    self.occupied_segments[(n_o, n_d)] = train.train_id

        # 2. Execució
        for i, (train, action) in enumerate(zip(self.trains, actions)):
            if train.done: continue
            seg = train.current_segment()
            if not seg: train.done = True; continue

            n_o, n_d = normalize_name(seg[0]), normalize_name(seg[1])
            base_time = NORMALIZED_TIMES.get((n_o, n_d), 4)
            is_blocked = (n_o, n_d) in self.occupied_segments and self.occupied_segments[(n_o, n_d)] != train.train_id

            # Lògica Recompensa simplificada
            reward = 0
            if action == 3: # Apartar
                if n_o in self.siding_stations:
                    train.waiting_at_station = True
                    reward -= 2
                    train.wait_time += 1
                    rewards[i] = reward
                    continue # No avança
                else:
                    reward -= 20
            
            if is_blocked:
                train.waiting_at_station = True
                reward -= 50
                rewards[i] = reward
                continue

            train.waiting_at_station = False
            
            # Moviment
            delta = -1 if action == 0 else (1 if action == 2 else 0)
            travel = max(1, base_time + delta)
            if random.random() < self.p_inc: travel += 5
            
            train.last_departure_time = train.real_time
            train.real_time += travel + Datas.STOP_STA_TIME
            train.scheduled_time += base_time + Datas.STOP_STA_TIME
            train.idx += 1
            
            # Reward per puntualitat
            diff = train.real_time - train.scheduled_time
            if abs(diff) <= 1: reward += 100
            else: reward -= abs(diff) * 10
            rewards[i] = reward

            if train.idx >= len(train.route) - 1: train.done = True

        next_states = [self.get_state(t) for t in self.trains]
        return next_states, rewards, all(t.done for t in self.trains)


class RodaliesAI:
    # --- CONFIGURACIÓ DEL SISTEMA DE TEMPS ---
    TIME_SCALE = 10.0      # 1 segon real = 10 minuts simulats
    SPAWN_INTERVAL = 30    # Cada quants minuts simulats surt un tren

    #RESET_INTERVAL = 1440  # Cada quants minuts es reseteja la via (24h)
    #CHAOS_INTERVAL = 600   # Cada quants minuts hi ha incidents (10h)

    RESET_INTERVAL = 210  # Cada quants minuts es reseteja la via (3.5h)
    CHAOS_INTERVAL = 60   # Cada quants minuts hi ha incidents (1h)
    
    def __init__(self, mode="visual"):
        self.mode = mode
        self.running = True
        
        # [MODIFICACIÓ] Inicialització Pygame només en mode visual
        if self.mode == "visual":
            pygame.init()
            self.width, self.height = 1400, 900
            self.screen = pygame.display.set_mode((self.width, self.height))
            #self.screen = pygame.display.toggle_fullscreen()
            pygame.display.set_caption("Rodalies AI - Q-Learning Train Control")
            self.clock = pygame.time.Clock()

        # Estructures de dades
        self.nodes = {}
        self.all_edges = []
        self.active_trains = []
        
        # [MODIFICACIÓ] El cervell es gestiona per tren, aquí només per referència si calgués
        # self.brain = ... (ara dins de Train)

        # --- SISTEMA DE TEMPS UNIFICAT ---
        # Tot s'inicialitza a 0.0 (minuts de simulació)
        self.sim_time = 0.0
        
        # Timers sincronitzats amb el temps de simulació, no amb el de la CPU
        self.last_chaos = self.sim_time
        self.last_reset = self.sim_time
        self.last_spawn = self.sim_time

        # [MODIFICACIÓ] Carreguem dades (adaptat per Datas.py)
        if self.mode == "visual":
            self.load_real_data()

    """
    ############################################################################################
    ############################################################################################

    Funcions per:
     - carregar dades reals d'estacions i coordenades
     - construir la línia R1 
     - contruir linies addicionals (si es vol)

    ############################################################################################
    ############################################################################################
    
    """


    ############################################################################################
    ################   Codi per passar de csv a format intern   #################################
    ############################################################################################
    def _normalize_name(self, name):
        # [COMENTARI ORIGINAL] Wrapper a la funció global nova
        return normalize_name(name)

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

    ############################################################################################
    ############################   LOADS DE LINIES   ###########################################
    ############################################################################################
    def load_real_data(self):
        # [MODIFICACIÓ] Usem Datas.py per saber quines estacions volem
        wanted_stations = set(normalize_name(s) for s in Datas.R1_STA)

        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        if not os.path.exists(csv_path): return
        
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
        
        # [MODIFICACIÓ] Marges de seguretat
        margin = 100
        safe_w = self.width - 2*margin
        safe_h = self.height - 2*margin

        for st in temp_st:
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * safe_w + margin
            y = safe_h - (((st['lat'] - min_lat) / (max_lat - min_lat)) * safe_h) + margin
            
            # [IMPORTANT] La clau del diccionari nodes és el nom normalitzat
            node = Node(x, y, st['norm'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            self.nodes[st['norm']] = node

        self.build_R1_from_datas()


    ############################################################################################
    ############################   Un cop tenim info, carreguem  ###############################
    ############################################################################################
    def build_R1_from_datas(self):
        # [MODIFICACIÓ] Construcció basada en Datas.R1_TIME
        for (s1, s2), t in Datas.R1_TIME.items():
            n1 = normalize_name(s1)
            n2 = normalize_name(s2)
            if n1 in self.nodes and n2 in self.nodes:
                u, v = self.nodes[n1], self.nodes[n2]
                
                # Creem aresta d'anada
                e0 = Edge(u, v, EdgeType.NORMAL, 0)
                e0.expected_minutes = t
                self.all_edges.append(e0)
                if v.id not in u.neighbors: u.neighbors[v.id] = []
                u.neighbors[v.id].append(e0)
                
                # Creem aresta de tornada (necessària visualment)
                e1 = Edge(v, u, EdgeType.NORMAL, 1)
                e1.expected_minutes = t
                self.all_edges.append(e1)
                if u.id not in v.neighbors: v.neighbors[u.id] = []
                v.neighbors[u.id].append(e1)

    """
    ############################################################################################
    ############################################################################################

    Funcions de Gestió ferroviària per
     - Calcular horaris
     - Spawn de trens

    ############################################################################################
    ############################################################################################   
    """

    def spawn_train_visual(self):
        # [MODIFICACIÓ] Spawn basat en la classe Train nova i nodes visuals
        t_id = len(self.active_trains)
        new_train = Train(train_id=t_id, start_delay=self.sim_time)
        
        # Injectem dades visuals (Nodes) a la lògica del tren
        start_name = normalize_name(new_train.route[0])
        
        if start_name in self.nodes:
            new_train.node = self.nodes[start_name]
            # Configurem el target inicial
            if len(new_train.route) > 1:
                next_name = normalize_name(new_train.route[1])
                if next_name in self.nodes:
                    new_train.target = self.nodes[next_name]
                    # Busquem l'edge
                    if new_train.target.id in new_train.node.neighbors:
                         new_train.current_edge = new_train.node.neighbors[new_train.target.id][0]

        # Carreguem cervell si existeix (global per visualització)
        if os.path.exists("q_table_global.pkl"):
            new_train.agent.load_table("q_table_global.pkl")
            
        self.active_trains.append(new_train)


    """
    ############################################################################################
    ############################################################################################

    Funcions de Pygame per la simulació i gestió del temps:
     - handle_mechanics : Gestiona esdeveniments Aleatoris (trancament de trens/vies, reseteig diari)
     - run : Bucle principal de la simulació

    ############################################################################################
    ############################################################################################   
    """
    def handle_mechanics(self):
        """Gestiona esdeveniments basats en el temps de simulació."""
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
            TrafficManager.reset()
            print(f"Dia nou: Vies i Incidències netejades al minut {int(self.sim_time)}")
        
        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
            self.last_chaos = self.sim_time
            # ... (Lògica d'incidents original o simplificada) ...

    def update_visuals(self, dt_sim):
        # [NOU] Lògica d'interpolació visual entre passos discrets de l'agent
        for t in self.active_trains:
            if t.finished: continue
            
            # Temps total del segment actual
            total_time = t.real_time - t.last_departure_time
            if total_time <= 0: total_time = 1
            
            # Progrés
            time_passed = self.sim_time - t.last_departure_time
            t.progress = time_passed / total_time
            
            # Si arriba al final del segment, STEP lògic de l'agent
            if t.progress >= 1.0:
                # 1. Obtenir estat visual
                seg = t.current_segment()
                if not seg: 
                    t.finished = True; t.done = True; continue
                
                n_o, n_d = normalize_name(seg[0]), normalize_name(seg[1])
                diff = t.real_time - t.scheduled_time
                state = (n_o, n_d, diff, 0) # Assumim no bloqueig en visual
                
                # 2. Acció agent
                action = t.agent.get_action(state) if hasattr(t.agent, 'get_action') else 1
                
                # 3. Calcular següent pas (Física)
                base = NORMALIZED_TIMES.get((n_o, n_d), 4)
                delta = -1 if action == 0 else (1 if action == 2 else 0)
                
                # 4. Actualitzar dades lògiques
                t.last_departure_time = self.sim_time
                t.real_time += max(1, base + delta) + Datas.STOP_STA_TIME
                t.idx += 1
                t.progress = 0.0
                
                # 5. Actualitzar dades visuals (Nodes)
                next_seg = t.current_segment()
                if next_seg:
                    u, v = normalize_name(next_seg[0]), normalize_name(next_seg[1])
                    if u in self.nodes and v in self.nodes:
                        t.node = self.nodes[u]
                        t.target = self.nodes[v]
                        if t.target.id in t.node.neighbors:
                            t.current_edge = t.node.neighbors[t.target.id][0]
                else:
                    t.finished = True


    def run(self):
        # [MODIFICACIÓ] Detectar si estem en mode visual realment
        if self.mode != "visual": return

        try:
            while self.running:
                dt_ms = self.clock.tick(60)       
                dt_sim = (dt_ms / 1000.0) * self.TIME_SCALE 
                self.sim_time += dt_sim

                # Events Input
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: self.running = False
                
                self.handle_mechanics()
                
                # Spawner simple
                if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
                    self.last_spawn = self.sim_time
                    self.spawn_train_visual()

                # Actualització Visual & Lògica Híbrida
                self.update_visuals(dt_sim)

                # Dibuix
                self.screen.fill((240, 240, 240))
                for e in self.all_edges: e.draw(self.screen)
                for n in self.nodes.values(): n.draw(self.screen)
                for t in self.active_trains: t.draw(self.screen)
                
                # HUD Debug
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
            import traceback
            traceback.print_exc()
        finally:
            pygame.quit()
            print("Simulació finalitzada.")

if __name__ == "__main__":
    # [NOU] Selector de mode
    print("1. Entrenar (Sense Gràfics)")
    print("2. Visualitzar (Pygame)")
    sel = input("Opció: ")
    
    if sel == "1":
        # Entrenament Multi-Agent
        env = MultiAgentR1Environment(num_trains=6)
        print("Entrenant...")
        for ep in range(2000): # Exemple
            states = env.reset()
            while not all(t.done for t in env.trains):
                actions = []
                for i, t in enumerate(env.trains):
                    st = states[i]
                    # Acció agent
                    act = t.agent.get_action(st) if hasattr(t.agent, 'get_action') else 1
                    actions.append(act)
                
                next_states, rewards, done = env.step(actions)
                
                # Update Agents
                for i, t in enumerate(env.trains):
                    if states[i] and not t.done:
                        t.agent.update(states[i], actions[i], rewards[i], next_states[i])
                states = next_states
            
            if ep % 100 == 0: print(f"Episodi {ep}")
        
        # Guardar (Usem el primer agent com a mostra global)
        env.trains[0].agent.save_table("q_table_global.pkl")
        
    else:
        RodaliesAI().run()