import pygame
import math
import random
from Enviroment.Datas import Datas
from Enviroment.TrafficManager import TrafficManager 

class Train:
    """
    Classe que representa un tren individual.
    Refactoritzada per utilitzar Estats Generalitzats (Distància/Velocitat) en lloc de Noms d'Estació.
    """
    # --- Constants Físiques ---
    ACCELERATION = 80.0    
    BRAKING = 150.0         
    MAX_SPEED_TRAIN = 120.0 
    BRAKING_DISTANCE_KM = 0.1

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
        

        # No mirem si som allà "ara", sinó quan trigarem a arribar-hi.
        
        remaining_dist_km = self.total_distance - self.distance_covered
        
        # Estimem la velocitat: Si estem parats, assumim la velocitat de la via (ex: 90%)
        # Si ja ens movem ràpid, usem la velocitat actual.
        if self.current_speed > 10:
            # Si anem lents però lluny, assumim que accelerarem fins a la velocitat de la via
            projected_speed = max(self.current_speed, self.max_speed_edge * 0.8)
        else:
            projected_speed = self.max_speed_edge * 0.9 # Suposició optimista per arrencar
            
        if projected_speed <= 0: projected_speed = 1.0 # Evitar divisió per zero

        # Temps estimat en minuts per recórrer el que falta
        time_needed_min = (remaining_dist_km / projected_speed) * 60
        
        projected_arrival_time = self.sim_time + time_needed_min
        
        # El retard és la diferència entre quan PREVEIEM arribar i quan l'horari diu
        return projected_arrival_time - expected_arrival

    # ---------------- ESTAT GENERALITZAT (EL SECRET DEL CANVI) ----------------
    def _get_general_state(self):
        """
        Converteix la situació actual en un estat genèric.
        L'agent ja no sap a 'Sants' o 'Mataró', només sap:
        - Quanta % de distància li queda.
        - A quina velocitat va.
        - Si va tard o d'hora.
        """
        """
        Estat: (Segment_ID, Distància_50, Velocitat_10, Retard)
        """
        
        # 1. IDENTIFICADOR DEL SEGMENT (El canvi que demanes)
        # Creem un string únic per a aquest parell d'estacions
        if self.node and self.target:
            # Ex: "BARCELONA-SANTS->PLACA DE CATALUNYA"
            segment_id = self.agent.get_segment_id(self.node.name, self.target.name) 
            # Nota: Si no vols crear un mètode al agent, pots fer directament:
            # segment_id = f"{self.node.name}->{self.target.name}"
        else:
            segment_id = "FI_TRAJECTE"

        # 2. DISTÀNCIA (Mantenim els 50 nodes per precisió)
        if self.total_distance > 0:
            pct = self.distance_covered / self.total_distance
            dist_state = int(pct * 50)  # 50 trams
            if dist_state > 49: dist_state = 49
        else:
            dist_state = 49
            
        # 3. VELOCITAT (Necessària per la física)
        speed_state = int(self.current_speed / 10.0)
        if speed_state > 12: speed_state = 12
        
        # 4. RETARD (El que volies)
        delay = self.calculate_delay()
        diff_disc = self.agent.discretize_diff(int(delay))
        
        # Opcional: Bloqueig (si vols mantenir-ho)
        tid = self.current_edge.track_id if self.current_edge else 0
        is_blocked = TrafficManager.check_alert(self.node.name, self.target.name, tid)
        
        # ESTAT FINAL COMBINAT
        return (segment_id, dist_state, speed_state, diff_disc, is_blocked)
    
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

    # ---------------- UPDATE PRINCIPAL ----------------
    def update(self, dt_minutes):
        reward = 0
        if self.finished: return
        
        # --- SISTEMA ANTIBLOQUEIG (NO MATAR, FORÇAR) ---
        current_delay_check = self.calculate_delay()
        
        # Variable per saber si hem d'intervenir manualment
        force_action_idx = None 

        if current_delay_check > 60:
            # 1. Castiguem l'agent: Li diem "Això està fatal"
            if self.is_training:
                state = self._get_general_state()
                # Li passem acció 2 (Frenar/No fer res) com a causa del càstig, 
                # per ensenyar-li que quedar-se parat amb tant retard és terrible.
                self.agent.update(state, 2, -100, None) 
            
            # 2. DECISIÓ DIVINA: Si no estem en una estació, t'obligo a córrer.
            if not self.is_waiting and self.is_training:
                force_action_idx = 0 # 0 = ACCELERAR (Override)
            
            # NOTA: NO hi ha 'return'. Deixem que el codi segueixi fluint.
        # -----------------------------

        # Gestió d'espera a l'estació (ARA SÍ QUE S'EXECUTARÀ SEMPRE)
        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                self.depart_from_station()
            return 

        # --- PAS 1: OBSERVAR ---
        state = self._get_general_state()
        
        # --- PAS 2: ACCIÓ ---
        # Si tenim una ordre forçada (pel retard), la usem. Si no, deixem decidir a l'agent.
        if force_action_idx is not None and self.is_training:
            action_idx = force_action_idx
        else:
            action_idx = self.agent.action(state)

        # [KICKSTART] Si estem parats a la via (v < 1) i l'agent no accelera, 
        # li donem una petita empenta aleatòria perquè no es quedi buclejat.
        if self.current_speed < 1.0 and action_idx != 0:
            if random.random() < 0.5: 
                action_idx = 0
                

        # --- PAS 3: FÍSICA OBLIGATÒRIA (SEGURETAT) ---
        # Si s'acaba la via, frenem sí o sí, digui el que digui l'agent o l'override.
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            pct_dist = dist_remaining / self.BRAKING_DISTANCE_KM
            target_approach_speed = pct_dist * 80.0 + 15.0 
            
            if self.current_speed > target_approach_speed:
                self.current_speed = target_approach_speed
                action_idx = 2 # Forcem acció 'Frenar' per a l'aprenentatge visual

        # --- PAS 4: EXECUTAR ---
        if action_idx == 0: self.accelerate(dt_minutes)
        elif action_idx == 1: pass 
        elif action_idx == 2: self.brake(dt_minutes)
            
        self.move(dt_minutes)
        self.sim_time += dt_minutes
        
        progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        TrafficManager.update_train_position(self.current_edge, self.id, progress_pct)

        # --- PAS 5: APRENDRE ---
        new_delay = self.calculate_delay()
        reward += -1.0 
        if abs(new_delay) > 2: reward -= 0.5

        if self.distance_covered >= self.total_distance:
            # Recompenses d'arribada (igual que abans)
            if abs(new_delay) <= 2: 
                reward += 100 
            else:
                reward += 10 
                reward -= min(50, abs(new_delay) * 2)
            self.arrive_at_station_logic()
        
        if self.is_training:
            if self.finished:
                new_state = None
            else:
                new_state = self._get_general_state()

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