import pygame
import math
from .EdgeType import EdgeType
from .TrafficManager import TrafficManager 

class TrainStatus:
    SENSE_RETARD = "ON TIME"     
    RETARD_MODERAT = "DELAYED"   
    AVARIAT = "BROKEN"           

class Train:
    # --- CONFIGURACIÓ FÍSICA ---
    ACCELERATION = 30.0   # km/h per minut (acceleració suau)
    BRAKING = 80.0        # km/h per minut (frenada forta)
    MAX_SPEED_DEF = 160.0 # Velocitat màxima per defecte
    SAFE_DISTANCE_PCT = 0.05 # 5% del tram com a distància de seguretat crítica

    def __init__(self, agent, route_nodes, scheduled_times, start_time_sim):
        self.agent = agent
        self.route = route_nodes
        self.schedule = scheduled_times 
        self.start_time = start_time_sim 
        
        # Identificació única per al TrafficManager (fent servir la instància com a ID o un hash)
        self.id = id(self) 

        self.route_index = 0
        self.node = self.route[0]
        self.target = self.route[1]
        
        self.current_time_accumulated = 0 
        self.status = TrainStatus.SENSE_RETARD
        
        # Sistema de Retards
        self.delay_global = 0.0   
        self.delay_segment = 0.0  
        self.segment_start_time = 0.0 
        
        # Estat de moviment
        self.finished = False
        self.progress = 0.0
        self.current_edge = None
        self.current_speed_kmh = 0.0 # Comença parat
        self.collision_detected = False

        self.setup_segment()

    def setup_segment(self):
        """Prepara el tren per entrar en un nou tram (Edge)"""
        if self.target.id in self.node.neighbors:
            possible_edges = self.node.neighbors[self.target.id]
            
            # 1. Consultar estat al TrafficManager
            state = self.get_state(possible_edges)
            action = self.agent.choose_action(state)
            
            self.current_edge = possible_edges[action]
            self.progress = 0.0
            self.segment_start_time = self.current_time_accumulated
            
            # Registrem la posició inicial
            TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
        else:
            self.finished = True
            TrafficManager.remove_train(self.id)

    def get_state(self, edges):
        """Obté l'estat actual per a l'agent RL"""
        s0 = edges[0].edge_type
        s1 = edges[1].edge_type
        
        # Consultes al TrafficManager (alertes estàtiques)
        alert0 = TrafficManager.check_alert(self.node.id, self.target.id, 0)
        alert1 = TrafficManager.check_alert(self.node.id, self.target.id, 1)
        
        return (self.node.id, self.target.id, s0, s1, alert0, alert1)

    def update(self, dt_minutes):
        """Bucle principal de física i lògica del tren"""
        if self.finished: return
        if self.collision_detected: return # Si està xocat, no es mou

        self.current_time_accumulated += dt_minutes
        
        # --- 1. SENSORS (PERCEPCIÓ) ---
        # Preguntem qui tenim davant
        dist_ahead = TrafficManager.get_nearest_train_ahead(
            self.current_edge, self.progress, self.id
        )
        
        # Preguntem si hi ha avisos a la via
        obstacle_alert = TrafficManager.check_alert(self.node.id, self.target.id, self.current_edge.track_id)

        # --- 2. DECISIÓ (TARGET SPEED) ---
        target_speed = self.current_edge.max_speed_kmh
        
        # Prioritat 1: Col·lisió Imminent
        if dist_ahead is not None:
            if dist_ahead < 0.01: # XOC! (Molt a prop, menys d'1% del tram)
                self.handle_collision()
                return
            elif dist_ahead < self.SAFE_DISTANCE_PCT:
                target_speed = 0.0 # FRENADA D'EMERGÈNCIA
            elif dist_ahead < (self.SAFE_DISTANCE_PCT * 4):
                target_speed = 25.0 # Mantenir distància (velocitat cautelar)
        
        # Prioritat 2: Obstacles a la via (avisos del TrafficManager)
        if obstacle_alert and target_speed > 15.0:
            target_speed = 15.0

        # --- 3. ACTUACIÓ (FÍSICA) ---
        # Accelerar o frenar cap a la velocitat objectiu
        if self.current_speed_kmh < target_speed:
            self.current_speed_kmh += self.ACCELERATION * dt_minutes
            if self.current_speed_kmh > target_speed: 
                self.current_speed_kmh = target_speed
        elif self.current_speed_kmh > target_speed:
            self.current_speed_kmh -= self.BRAKING * dt_minutes
            if self.current_speed_kmh < target_speed: 
                self.current_speed_kmh = target_speed

        # Calcular desplaçament
        # Distància (km) = Velocitat (km/h) * Temps (h)
        distance_km = self.current_speed_kmh * (dt_minutes / 60.0)
        
        edge_length_km = self.current_edge.real_length_km
        if edge_length_km > 0:
            self.progress += distance_km / edge_length_km
        else:
            self.progress = 1.0

        # --- 4. ACTUALITZACIÓ AL SISTEMA CENTRAL ---
        TrafficManager.update_train_position(self.current_edge, self.id, self.progress)

        # Reportar lentitud al TrafficManager si cal
        expected_time = self.current_edge.expected_minutes
        current_segment_time = self.current_time_accumulated - self.segment_start_time
        if expected_time > 0 and current_segment_time > (expected_time * 3):
            TrafficManager.report_issue(self.node.id, self.target.id, self.current_edge.track_id)

        # Calcular retards globals
        target_schedule = self.schedule.get(self.target.id, 0)
        current_clock_time = self.start_time + self.current_time_accumulated
        self.delay_global = max(0, current_clock_time - target_schedule)
        
        # Actualitzar estat visual
        if not self.collision_detected:
            if self.delay_global < 5: self.status = TrainStatus.SENSE_RETARD
            elif self.delay_global < 15: self.status = TrainStatus.RETARD_MODERAT
            else: self.status = TrainStatus.AVARIAT

        # Final de tram
        if self.progress >= 1.0:
            self.arrive_at_station()

    def handle_collision(self):
        """Gestiona el xoc: atura el tren i penalitza fortament l'agent."""
        print(f"!!! COL·LISIÓ DETECTADA: Tren {self.id} ha xocat a {self.current_edge} !!!")
        self.collision_detected = True
        self.status = TrainStatus.AVARIAT
        self.current_speed_kmh = 0.0
        
        # Penalització massiva per aprendre a evitar-ho
        reward = -1000.0 
        
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        action = self.current_edge.track_id 
        
        # L'estat següent és el mateix (s'ha quedat atrapat)
        self.agent.learn(state, action, reward, state)

    def arrive_at_station(self):
        # 1. Netejar posició del tram anterior
        TrafficManager.remove_train(self.id)

        actual_duration = self.current_time_accumulated - self.segment_start_time
        ideal_duration = (self.current_edge.real_length_km / 160.0) * 60
        if ideal_duration == 0: ideal_duration = 0.1
        
        self.delay_segment = actual_duration - ideal_duration

        # Si hem anat bé, netegem alertes antigues
        if self.delay_segment < 2.0: 
             TrafficManager.clear_issue(self.node.id, self.target.id, self.current_edge.track_id)

        # --- CÀLCUL DE RECOMPENSA ---
        reward = 0
        
        # Recompensa base per arribar
        if self.delay_segment > 0: reward -= (self.delay_segment * 10) 
        else: reward += 10 
            
        if self.delay_global > 10: reward -= 20 
        if self.delay_segment > 15: reward -= 200 

        # Aprenentatge RL
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        action = self.current_edge.track_id 
        
        # Obtenim el següent estat teòric per l'algorisme (encara que ara canviarem de node)
        # Simplificació: assumim que el next_state és l'arribada (o el nou node)
        next_state = state 
        
        self.agent.learn(state, action, reward, next_state)

        # Canvi de node
        self.node = self.target
        self.route_index += 1
        
        if self.route_index < len(self.route) - 1:
            self.target = self.route[self.route_index + 1]
            self.setup_segment()
        else:
            self.finished = True
            # Ja no cal fer remove_train perquè l'hem fet al principi de la funció

    def draw(self, screen):
        if self.finished: return
        
        # Color segons estat
        color = (0, 200, 0) 
        if self.status == TrainStatus.RETARD_MODERAT: color = (230, 140, 0) 
        if self.status == TrainStatus.AVARIAT: color = (200, 0, 0) 
        if self.collision_detected: color = (0, 0, 0) # Negre si ha xocat
        
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        # Offset visual per separar les dues vies
        off = 5 if self.current_edge.track_id == 0 else -5
        
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Assegurem que no dibuixa fora del segment (max 1.0)
        safe_progress = min(1.0, self.progress)
        
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)
        
        # Opcional: Dibuixar velocitat sobre el tren per debug
        # font = pygame.font.SysFont("Arial", 10)
        # text = font.render(f"{int(self.current_speed_kmh)}", True, (0,0,0))
        # screen.blit(text, (cur_x + 10, cur_y - 10))