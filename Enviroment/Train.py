import pygame
import math
import random
from Enviroment.Datas import Datas
from Enviroment.TrafficManager import TrafficManager 

class Train:
    """
    Classe que representa un tren individual.
    """
    # --- Constants Físiques ---
    ACCELERATION = 80.0    
    BRAKING = 150.0         
    MAX_SPEED_TRAIN = 120.0 
    BRAKING_DISTANCE_KM = 0.2 

    def __init__(self, agent, route_nodes, schedule, start_time_sim, is_training=False):
        self.agent = agent
        self.route_nodes = route_nodes
        self.schedule = schedule
        self.is_training = is_training

        self.id = id(self)
        self.finished = False
        
        self.current_node_idx = 0
        self.node = self.route_nodes[0]
        self.target = self.route_nodes[1] if len(route_nodes) > 1 else None
        
        # Registre d'arribades
        self.arrival_logs = {} 
        if self.node:
            self.arrival_logs[self.node.name] = start_time_sim

        self.current_speed = 0.0
        self.distance_covered = 0.0
        self.total_distance = 1.0
        self.max_speed_edge = 90.0
        
        self.sim_time = start_time_sim
        
        self.is_waiting = False    
        self.wait_timer = 0.0      
        self.WAIT_TIME_MIN = Datas.STOP_STA_TIME   

        self.setup_segment()

    def setup_segment(self):
        if not self.target:
            self.finished = True
            return

        # (Import local eliminat, fem servir el global)
        edge = TrafficManager.get_edge(self.node.name, self.target.name)
        
        if edge:
            self.current_edge = edge
            self.total_distance = edge.real_length_km
            self.max_speed_edge = edge.max_speed_kmh
        else:
            self.current_edge = None
            self.total_distance = 2.0 
            self.max_speed_edge = 80.0
            
        self.distance_covered = 0.0
        self.current_speed = 0.0 

    def calculate_delay(self):
        if not self.target: return 0
        expected_arrival = self.schedule.get(self.target.id)
        if expected_arrival is None: return 0
        return self.sim_time - expected_arrival

    # ---------------- FÍSICA ----------------
    def accelerate(self, dt_minutes):
        self.current_speed += self.ACCELERATION * dt_minutes
        limit = min(self.MAX_SPEED_TRAIN, self.max_speed_edge)
        if self.current_speed > limit:
            self.current_speed = limit

    def brake(self, dt_minutes):
        self.current_speed -= self.BRAKING * dt_minutes
        if self.current_speed < 0:
            self.current_speed = 0

    def move(self, dt_minutes):
        distance_step = self.current_speed * (dt_minutes / 60.0)
        self.distance_covered += distance_step

    # ---------------- UPDATE ----------------
    def update(self, dt_minutes):
        if self.finished: return
        
        # --- KILL SWITCH CORREGIT ---
        current_delay_check = self.calculate_delay()
        if current_delay_check > 60:
            if self.is_training:
                # Penalització per mort
                prev_delay = self.calculate_delay()
                prev_diff_disc = self.agent.discretize_diff(int(prev_delay))
                tid = self.current_edge.track_id if self.current_edge else 0
                state = (self.node.name, self.target.name if self.target else "Fi", prev_diff_disc, 0)
                
                self.agent.update(state, 2, -1000, None)
            
            self.finished = True
            # (Import local eliminat)
            TrafficManager.remove_train(self.id)
            return
        # -----------------------------

        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                self.depart_from_station()
            return 

        # --- PAS 1: OBSERVAR ---
        prev_delay = self.calculate_delay()
        prev_diff_disc = self.agent.discretize_diff(int(prev_delay))
        tid = self.current_edge.track_id if self.current_edge else 0
        
        # (Import local eliminat)
        is_blocked = TrafficManager.check_alert(self.node.name, self.target.name, tid)
        
        state = (self.node.name, self.target.name, prev_diff_disc, is_blocked)
        
        # --- PAS 2: ACCIÓ ---
        action_idx = self.agent.action(state)
        # ==============================================================================
        # [NOU] KICKSTART: Evitar que l'agent aprengui a quedar-se quiet a la via
        # ==============================================================================
        # Si la velocitat és gairebé 0, NO estem esperant a l'estació, i l'acció no és accelerar:
        if self.current_speed < 1.0 and not self.is_waiting and action_idx != 0:
            # Forcem l'acceleració amb una probabilitat alta (ex: 50% o 100% al principi)
            # Això trenca la "passivitat" inicial.
            if random.random() < 0.5: 
                action_idx = 0

        # --- PAS 3: FÍSICA OBLIGATÒRIA (Anti-Trompades) ---
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            pct_dist = dist_remaining / self.BRAKING_DISTANCE_KM
            target_approach_speed = pct_dist * 80.0 + 2.0
            if self.current_speed > target_approach_speed:
                self.current_speed = target_approach_speed
                action_idx = 2 

        # --- PAS 4: EXECUTAR ---
        if action_idx == 0: self.accelerate(dt_minutes)
        elif action_idx == 1: pass 
        elif action_idx == 2: self.brake(dt_minutes)
            
        self.move(dt_minutes)
        self.sim_time += dt_minutes
        
        progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        TrafficManager.update_train_position(self.current_edge, self.id, progress_pct)

        # --- PAS 5: APRENDRE ---
        
        # 1. Calculem l'estat següent "per defecte" (el tren segueix viu)
        #    Això s'ha de fer SEMPRE, estigui arribant o no.
        new_delay = self.calculate_delay()
        new_diff_disc = self.agent.discretize_diff(int(new_delay))
        
        # [CRÍTIC] Definim new_state aquí perquè existeixi sempre
        new_state = (self.node.name, self.target.name, new_diff_disc, is_blocked)
        
        # 2. Recompensa base (existència/temps)
        reward = -1.0 
        if abs(new_delay) > 2: reward -= 0.5

        # 3. Gestió d'arribada a l'estació
        if self.distance_covered >= self.total_distance:
            # Recompenses finals d'aquest tram
            if abs(new_delay) <= 2: 
                reward += 100 
            else:
                reward += 10 
                reward -= min(50, abs(new_delay) * 2)
            
            # Canviem físicament d'estació
            self.arrive_at_station_logic()
            
            # [CRÍTIC] Només si el tren ha acabat TOTALMENT la ruta, l'estat futur és None
            if self.finished:
                new_state = None
        
        # 4. Actualització de la Q-Table
        if self.is_training:
            # Ara new_state sempre té valor (o la tupla o None)
            self.agent.update(state, action_idx, reward, new_state)

    def arrive_at_station_logic(self):
        self.current_speed = 0.0 
        self.distance_covered = self.total_distance 
        
        if self.target:
            self.arrival_logs[self.target.name] = self.sim_time

        self.is_waiting = True
        self.wait_timer = self.WAIT_TIME_MIN

    def depart_from_station(self):
        self.is_waiting = False
        self.current_node_idx += 1
        self.node = self.target
        
        if self.current_node_idx < len(self.route_nodes) - 1:
            self.target = self.route_nodes[self.current_node_idx + 1]
            self.setup_segment()
        else:
            self.finished = True
            self.target = None
            # (Import local eliminat)
            TrafficManager.remove_train(self.id)

    def draw(self, screen):
        if self.finished or not self.node or not self.target: return

        if self.is_waiting:
            color = (255, 200, 0) 
        else:
            delay = self.calculate_delay()
            if abs(delay) <= 2: color = (0, 255, 0)
            elif delay > 2:     color = (255, 0, 0)
            else:               color = (0, 0, 255)

        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        off = 0 
            
        dx = end_x - start_x
        dy = end_y - start_y
        dist_px = math.sqrt(dx**2 + dy**2)
        if dist_px == 0: dist_px = 1
        
        perp_x = -dy / dist_px
        perp_y = dx / dist_px
        
        progress = self.distance_covered / self.total_distance
        progress = max(0.0, min(1.0, progress))
        
        cur_x = start_x + dx * progress + perp_x * off
        cur_y = start_y + dy * progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)

    def __repr__(self):
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"

    def debug_status(self):
        delay = self.calculate_delay()
        estat_str = "A TEMPS"
        if delay > 2: estat_str = f"RETARD (+{delay:.1f}m)"
        elif delay < -2: estat_str = f"AVANÇAT ({delay:.1f}m)"
        
        print(f"=== DEBUG TREN {self.id} ===")
        print(f"📍 Posició: {self.distance_covered:.2f}/{self.total_distance:.2f} km")
        print(f"🚄 Velocitat: {self.current_speed:.1f} km/h")
        print(f"⏱️  Estat: {estat_str} | SimTime: {self.sim_time:.1f}")
        print("---------------------------")