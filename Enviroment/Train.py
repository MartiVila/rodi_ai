import pygame
import math
from .EdgeType import EdgeType
from .TrafficManager import TrafficManager 

class TrainStatus:
    SENSE_RETARD = "ON TIME"     
    RETARD_MODERAT = "DELAYED" # O "EARLY" en aquest cas
    AVARIAT = "BROKEN"           

class Train:
    # FÍSICA
    ACCELERATION = 30.0   
    BRAKING = 80.0        
    SAFE_DISTANCE_PCT = 0.05 

    """
    ############################################################################################
    ############################################################################################

    Classe base per crear Objectes trens gestionants per Qlearning Agent

    Els trens tenen un delay local i global

    ############################################################################################
    ############################################################################################
    
    """

    def __init__(self, agent, route_nodes, scheduled_times, start_time_sim):
        """
        Docstring for __init__
        
        :param agent: Instancia de Qlearning agent
        :param route_nodes: Ruta a seguir, llista de nodes 
        :param scheduled_times: Diccionari {node_id: time_in_minutes}
        :param start_time_sim: Temps d'inici de la simulació en minuts

        L'agent de tren és una instància compartida entre tots els trens, UN Agent
        Apren de TOTS els trens
        """
        self.agent = agent
        self.route = route_nodes
        self.schedule = scheduled_times 
        self.start_time = start_time_sim 
        self.id = id(self) 

        self.route_index = 0
        self.node = self.route[0]
        self.target = self.route[1]
        
        self.current_time_accumulated = 0 
        self.status = TrainStatus.SENSE_RETARD
        
        # Variables de control
        self.delay_global = 0.0   
        self.segment_start_time = 0.0 
        self.finished = False
        self.progress = 0.0
        self.current_edge = None
        self.current_speed_kmh = 0.0 
        self.collision_detected = False

        self.setup_segment()

    def setup_segment(self):
        """
        Mètode per a canvi de via
        """
        if self.target.id in self.node.neighbors:
            possible_edges = self.node.neighbors[self.target.id]
            state = self.get_state(possible_edges)
            action = self.agent.choose_action(state)
            
            self.current_edge = possible_edges[action]
            self.progress = 0.0
            self.segment_start_time = self.current_time_accumulated
            
            TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
        else:
            self.finished = True
            TrafficManager.remove_train(self.id)

    def get_state(self, edges):
        s0 = edges[0].edge_type
        s1 = edges[1].edge_type
        alert0 = TrafficManager.check_alert(self.node.id, self.target.id, 0)
        alert1 = TrafficManager.check_alert(self.node.id, self.target.id, 1)
        return (self.node.id, self.target.id, s0, s1, alert0, alert1)


    def update(self, dt_minutes):
        """
        Metode d'actualització del tren.
        Semblant al mètode heuristica de la pràctica anterior, 
        però ara integrat amb la xarxa ferroviària i el gestor de trànsit.

        Heuristica té dos parts:
            - Una està aquí
            -L'altre part és quan arribem a la estació
        
        :param dt_minutes: Delta de temps en minuts des de l'última actualització (Retard)
        """
        if self.finished: return
        if self.collision_detected: return 

        self.current_time_accumulated += dt_minutes
        
        # --- 1. CÀLCUL DE LA VELOCITAT DE PUNTUALITAT ---
        # Quant temps tenim assignat per aquest tram segons horari?
        # Expected minutes és atribut classe edge, es calcula al init
        scheduled_duration = self.current_edge.expected_minutes
        
        # Quant temps portem en aquest tram?
        elapsed_in_segment = self.current_time_accumulated - self.segment_start_time
        
        # Temps restant per arribar a l'hora exacta (target = 0 delay)
        time_remaining = scheduled_duration - elapsed_in_segment
        
        # Distància real restant (km)
        #TODO Realment està en distància real? No sé si estàn bé els pesos
        dist_total_km = self.current_edge.real_length_km
        dist_remaining_km = dist_total_km * (1.0 - self.progress)
        
        if dist_remaining_km <= 0:
            punctuality_speed = 10.0 # Ja estem, només cal acabar d'arribar
        elif time_remaining <= 0:
            # Anem tard! Velocitat màxima per intentar recuperar
            punctuality_speed = self.current_edge.max_speed_kmh
        else:
            # Velocitat necessària = Distància / Temps
            # Temps està en minuts, velocitat en km/h -> passem minuts a hores (/60)
            required_speed = dist_remaining_km / (time_remaining / 60.0)
            punctuality_speed = required_speed

        # Limitem la velocitat de puntualitat als límits físics de la via
        punctuality_speed = min(punctuality_speed, self.current_edge.max_speed_kmh)
        # Mínim 20 km/h perquè no s'aturi si va molt aviat (simplement va molt lent)
        punctuality_speed = max(punctuality_speed, 20.0)

        # --- 2. CÀLCUL DE LA VELOCITAT DE SEGURETAT ---
        dist_ahead = TrafficManager.get_nearest_train_ahead(
            self.current_edge, self.progress, self.id
        )
        obstacle_alert = TrafficManager.check_alert(self.node.id, self.target.id, self.current_edge.track_id)
        
        safety_speed = self.current_edge.max_speed_kmh # Per defecte màxima

        if dist_ahead is not None:
            if dist_ahead < 0.01: 
                self.handle_collision()
                return
            elif dist_ahead < self.SAFE_DISTANCE_PCT:
                safety_speed = 0.0 # STOP
            elif dist_ahead < (self.SAFE_DISTANCE_PCT * 4):
                safety_speed = 30.0 # Precaució
        
        if obstacle_alert:
            safety_speed = min(safety_speed, 15.0)

        # --- 3. FUSIÓ I ACTUACIÓ ---
        # La velocitat final és la més restrictiva de les dues
        target_speed = min(punctuality_speed, safety_speed)

        # Física: Accelerar/Frenar cap al target
        if self.current_speed_kmh < target_speed:
            self.current_speed_kmh += self.ACCELERATION * dt_minutes
            if self.current_speed_kmh > target_speed: 
                self.current_speed_kmh = target_speed
        elif self.current_speed_kmh > target_speed:
            self.current_speed_kmh -= self.BRAKING * dt_minutes
            if self.current_speed_kmh < target_speed: 
                self.current_speed_kmh = target_speed

        # Moure tren
        distance_km = self.current_speed_kmh * (dt_minutes / 60.0)
        if dist_total_km > 0:
            self.progress += distance_km / dist_total_km
        else:
            self.progress = 1.0

        TrafficManager.update_train_position(self.current_edge, self.id, self.progress)
        
        # Reportar obstacles lents (si anem molt més lents del previst per causa externa)
        # Només si la target speed era alta però anem lents
        if elapsed_in_segment > (scheduled_duration * 2):
             TrafficManager.report_issue(self.node.id, self.target.id, self.current_edge.track_id)

        # Actualitzar HUD de retard global (Informatiu)
        target_clock = self.schedule.get(self.target.id, 0)
        current_clock = self.start_time + self.current_time_accumulated
        self.delay_global = current_clock - target_clock # Pot ser negatiu (aviat) o positiu (tard)
        
        if abs(self.delay_global) < 2: self.status = TrainStatus.SENSE_RETARD
        else: self.status = TrainStatus.RETARD_MODERAT

        # HEURISTICA PART 2: Gestió delays
        if self.progress >= 1.0:
            self.arrive_at_station()


    def handle_collision(self):
        """
        Si estem apunt de Colisionar, es dona el tren per avariat i parem
        """
        print(f"!!! COL·LISIÓ Tren {self.id} !!!")
        self.collision_detected = True
        self.status = TrainStatus.AVARIAT
        self.current_speed_kmh = 0.0
        
        reward = -2000.0 # Penalització extrema
        
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        action = self.current_edge.track_id 
        self.agent.learn(state, action, reward, state)

    def arrive_at_station(self):
        """
        Gestió que fem cada cop que sortim d'una aresta/node
        Avisem a centrar (Traffic Manager) 
        HEURISTICA DE DELAYS
        Part2
        
        """
        TrafficManager.remove_train(self.id)

        # Càlcul precís del retard en l'arribada a l'estació
        target_arrival_time = self.schedule.get(self.target.id, 0)
        actual_arrival_time = self.start_time + self.current_time_accumulated
        
        # Retard Absolut (arribar aviat és tan dolent com arribar tard)
        delay = actual_arrival_time - target_arrival_time
        abs_delay = abs(delay)

        # Netejar incidències si hem anat raonablement bé
        if abs_delay < 5.0: 
             TrafficManager.clear_issue(self.node.id, self.target.id, self.current_edge.track_id)

        # --- RECOMPENSA BASADA EN RETARD ABSOLUT ---
        # Volem delay = 0. 
        # Si delay = 0, reward màxim (+100).
        # Per cada minut de desviació, restem punts.
        
        reward = 100.0 - (abs_delay * 10.0)
        
        # Penalització extra si és inacceptable (>15 minuts de desviació)
        if abs_delay > 15.0:
            reward -= 100.0

        # Aprenentatge
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        action = self.current_edge.track_id 
        next_state = state 
        
        self.agent.learn(state, action, reward, next_state)

        # Pas següent
        self.node = self.target
        self.route_index += 1
        
        if self.route_index < len(self.route) - 1:
            self.target = self.route[self.route_index + 1]
            self.setup_segment()
        else:
            self.finished = True

    def draw(self, screen):
        # (El draw es manté igual, pots fer servir el que ja tenies)
        if self.finished: return
        color = (0, 200, 0) 
        if abs(self.delay_global) > 5: color = (230, 140, 0) 
        if self.collision_detected: color = (0, 0, 0) 
        
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        off = 5 if self.current_edge.track_id == 0 else -5
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        safe_progress = min(1.0, self.progress)
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)