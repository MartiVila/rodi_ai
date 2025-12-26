import pygame
import math
import random
from Enviroment.Datas import Datas
from Enviroment.TrafficManager import TrafficManager 

class Train:
    """
    Agent autònom que representa un tren individual.
    Combina lògica física (cinemàtica) amb presa de decisions (RL Agent).
    """
    
    # --- Constants Físiques ---
    ACCELERATION = 80.0     # km/h per minut (Aprox 1.3 m/s^2)
    BRAKING = 150.0         # Frenada forta
    MAX_SPEED_TRAIN = 120.0 # Velocitat màxima del material rodant
    BRAKING_DISTANCE_KM = 0.1 # Distància de seguretat per frenar davant estació

    def __init__(self, agent, route_nodes, schedule, start_time_sim, is_training=False):
        """
        :param agent: Referència al QLearningAgent compartit.
        :param route_nodes: Llista d'objectes Node que formen la ruta.
        :param schedule: Diccionari {node_id: temps_arribada_previst}.
        :param start_time_sim: Hora d'inici de la simulació.
        """
        self.agent = agent
        self.route_nodes = route_nodes
        self.schedule = schedule
        self.is_training = is_training

        self.id = id(self)
        self.finished = False
        
        # Estat de Navegació
        self.current_node_idx = 0
        self.node = self.route_nodes[0] # Estació actual/origen
        self.target = self.route_nodes[1] if len(route_nodes) > 1 else None # Pròxima estació
        
        # Logs per l'informe final
        self.arrival_logs = {} 
        if self.node:
            self.arrival_logs[self.node.name] = start_time_sim

        # Estat Cinemàtic
        self.current_speed = 0.0
        self.distance_covered = 0.0
        self.total_distance = 1.0     # Es recalcularà al setup_segment
        self.max_speed_edge = 90.0    # Es recalcularà
        
        self.sim_time = start_time_sim
        
        # Estat d'Estació (Parada)
        self.is_waiting = False    
        self.wait_timer = 0.0      
        self.WAIT_TIME_MIN = Datas.STOP_STA_TIME   
        
        # [MODIFICACIÓ] Memòria per calcular velocitat relativa (tendència)
        self.last_dist_leader = float('inf')
        #Penalty acumulatiu per ús excesiu de ATP
        #ATP ha de ser només en cas d'emergència
        self.atp_penalty = 0.0

        #Inicialitzem el primer segment
        self.setup_segment()

    def setup_segment(self):
        """Configura les dades del tram de via actual (distància i velocitat màxima)."""
        if not self.target:
            self.finished = True
            return

        # Demanem al TrafficManager les dades físiques de la via
        edge = TrafficManager.get_edge(self.node.name, self.target.name)
        
        if edge:
            self.current_edge = edge
            self.total_distance = edge.real_length_km
            self.max_speed_edge = edge.max_speed_kmh
        else:
            # Fallback per seguretat
            self.current_edge = None
            self.total_distance = 2.0 
            self.max_speed_edge = 80.0
            
        self.distance_covered = 0.0
        #Conservem la velocitat actual (inèrcia) entre segments, 
        #tot i que normalment a l'estació és 0.

    """
    ############################################################################################
    ############################################################################################

    Mòdul d'Intel·ligència Artificial (Estats i Recompenses)

    ############################################################################################
    ############################################################################################
    """

    def calculate_delay(self):
        """
        Calcula el retard projectat a la pròxima estació.
        Retard = (Hora Actual + Temps Estimat Viatge) - Hora Prevista Horari
        """
        if not self.target: return 0
        expected_arrival = self.schedule.get(self.target.id)
        if expected_arrival is None: return 0
        
        remaining_dist_km = self.total_distance - self.distance_covered
        
        # Heurística de velocitat mitjana per estimar el temps restant
        if self.current_speed > 10:
            # Si ja ens movem, projectem que mantindrem o augmentarem velocitat
            projected_speed = max(self.current_speed, self.max_speed_edge * 0.8)
        else:
            # Si estem parats, som optimistes que arrencarem aviat
            projected_speed = self.max_speed_edge * 0.9 
            
        if projected_speed <= 0: projected_speed = 1.0 

        time_needed_min = (remaining_dist_km / projected_speed) * 60
        projected_arrival_time = self.sim_time + time_needed_min
        
        return projected_arrival_time - expected_arrival

    def _get_general_state(self):
        """
        Construeix el vector d'estat per a la Q-Table.
        #AQUI HE AUGMENTAT EN 1 ESTAT
        Vector: (Segment_ID, %_Distància, Velocitat, Retard, Bloqueig)
        """
        #id del segment, posicio del tren
        if self.node and self.target:
            segment_id = self.agent.get_segment_id(self.node.name, self.target.name) 
        else:
            segment_id = "FI_TRAJECTE"

        #distpancia discretitzada
        if self.total_distance > 0:
            pct = self.distance_covered / self.total_distance
            dist_state = int(pct * 50) 
            if dist_state > 49: dist_state = 49
        else:
            dist_state = 49
        
        #ARA MIRA LA SEGUENT VIA, DE MANERA QUE MILLORA LA PREDICCIÓ DE VELOCITAT DECIDIDA
        dist_leader = self.get_vision_ahead()

        #A 5 NIVELLS, discretitzem el nivell d'alerta que ha de considerar l'agent.
        if dist_leader > 4.0:
            proximity_state = 0 #no alerta
        elif dist_leader > 2.0:
            proximity_state = 1 #chill de moment
        elif dist_leader > 1.0:
            proximity_state = 2 #ull viu
        elif dist_leader > 0.4:
            proximity_state = 3 #s'acosta
        else:
            proximity_state = 4 #GERMÀ QUE XOQUEEEES

        #Hem de decidir la velocitat realtica tenint en compte les distàncies.
        diff = dist_leader - self.last_dist_leader
        if diff < -0.005:   #podem correr
            trend_state = 2 
        elif diff > 0.005:  #ens allunyem
            trend_state = 0
        else:               #mantenim distància
            trend_state = 1

        #velocitat discretitxada en nultiplers de 10
        speed_state = int(self.current_speed / 10.0)
        if speed_state > 12: speed_state = 12 #max 120, com a les autovies
        
        #retard discretitzat
        delay = self.calculate_delay()
        diff_disc = self.agent.discretize_diff(int(delay))
        
        #alerta de via bloquejada
        tid = self.current_edge.track_id if self.current_edge else 0
        is_blocked = TrafficManager.check_alert(self.node.name, self.target.name, tid)
        
        return (segment_id, dist_state, speed_state, diff_disc, is_blocked, proximity_state, trend_state)

    """
    ############################################################################################
    ############################################################################################

    Mòdul de Física (Update Logic)

    ############################################################################################
    ############################################################################################
    """

    def get_vision_ahead(self):
        """
        evitem punt secundari mirant a la següent via si estem a prop del final
        Retorna la distància al líder en la via actual o la suma de distàncies
        """
        #via actual
        dist = TrafficManager.get_distance_to_leader(self.current_edge, self.id)
        
        # Si no hi ha ningú davant (infinit) I estem a prop del final (>90% recorregut),
        # mirem la següent via.
        if dist == float('inf') and self.distance_covered > (self.total_distance * 0.9):
            # Identificar següent tram
            if self.current_node_idx + 1 < len(self.route_nodes) - 1:
                next_u = self.route_nodes[self.current_node_idx + 1] # El meu target actual
                next_v = self.route_nodes[self.current_node_idx + 2] # El següent al target
                
                next_edge = TrafficManager.get_edge(next_u.name, next_v.name)
                if next_edge:
                    # Busquem l'últim tren de la següent via (el que acaba d'entrar)
                    # La llista està ordenada per progrés descendent (el primer és el més avançat)
                    trains_next = TrafficManager._train_positions.get(next_edge, [])
                    if trains_next:
                        # L'últim de la llista és el que té menys progrés (cua de la via)
                        leader_id, leader_prog = trains_next[-1] 
                        
                        dist_to_end_of_current = self.total_distance - self.distance_covered
                        dist_of_leader_in_next = leader_prog * next_edge.real_length_km
                        
                        return dist_to_end_of_current + dist_of_leader_in_next

        return dist

    def accelerate(self, dt_minutes):
        self.current_speed += self.ACCELERATION * dt_minutes
        # Límits: La velocitat del tren o la de la via, la que sigui menor
        limit = min(self.MAX_SPEED_TRAIN, self.max_speed_edge)
        if self.current_speed > limit:
            self.current_speed = limit

    def brake(self, dt_minutes):
        self.current_speed -= self.BRAKING * dt_minutes
        if self.current_speed < 0:
            self.current_speed = 0

    def move(self, dt_minutes):
        # x = v * t
        distance_step = self.current_speed * (dt_minutes / 60.0)
        self.distance_covered += distance_step

    def update(self, dt_minutes):
        if self.finished: return
        self.atp_penalty = 0.0 #cada frame te un castig de atp nou

        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                self.depart_from_station()
            return 

        #millor visio
        dist_leader = self.get_vision_ahead()

        #observació
        state = self._get_general_state()
        current_delay = self.calculate_delay()
        
        #decisió
        action_idx = self.agent.action(state)
        '''
        ELIMINAT FORÇAT D'ENSENYAMENT (TRAINING)
         Comentat per evitar que la IA depengui d'ajudes hardcoded. 
         Que aprengui sola que accelerar és bo si no hi ha ningú.
         SEMBLA QUE FUNCIONA CORRECTAMENT
         if self.is_training:
             if dist_leader > 3.0 and action_idx != 0 and self.current_speed < self.max_speed_edge:
                 action_idx = 0  # Si hay >3km libres, fuerza acelerar
        '''
        #seguretat bàsica
        if current_delay > 60 and self.is_training:
             self.agent.update(state, 2, -100, None) 
             action_idx = 0
        if self.current_speed < 1.0 and action_idx != 0 and self.is_training:
            if random.random() < 0.5: action_idx = 0

        #frenem a l'estació
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            pct_dist = dist_remaining / self.BRAKING_DISTANCE_KM
            target_approach_speed = pct_dist * 80.0 + 15.0 
            if self.current_speed > target_approach_speed:
                self.current_speed = target_approach_speed
                action_idx = 2

        #execuciño fñisica de la decisió de l'agent
        if action_idx == 0: self.accelerate(dt_minutes)
        elif action_idx == 1: pass
        elif action_idx == 2: self.brake(dt_minutes)
            
        #AUTOMATIC TRAIN PROTECTION, ATP, SISTEMA DE SEGURETAT HUMANA
        #AQUESTA UTILITZACIÓ ÉS PENALITZADA, VOLEM QUE L'AGENT APRENGUI CORRECTAMENT
        #NOMÉS ÉS PER QUE NO MATI A NINGU EN CAS DE SER IMPLEMENTAT EN LA VIDA REAL
        dynamic_limit = self.max_speed_edge
        
        if dist_leader < float('inf'):
            if dist_leader < 0.5:     # Massa aprop
                dynamic_limit = 0.0   # STOP
            elif dist_leader < 1.5:   # Precaució: < 1.5km
                dynamic_limit = 30.0  # lentitud
            elif dist_leader < 3.0:   # Precaució: < 3km
                dynamic_limit = 60.0  # Moderat
            elif dist_leader < 5.0:   # Avis: < 5km
                dynamic_limit = 90.0  # Reduir una mica
            
            # Si es va massa ràpid, el sistema actua
            if self.current_speed > dynamic_limit:
                #Si ATP ha intervingut, es penalitza, aixi apren a millorar
                if self.is_training:
                    self.atp_penalty = -50.0 
                    
                #frenad automatica
                self.current_speed -= (self.BRAKING * 0.5) * dt_minutes
                if self.current_speed < dynamic_limit:
                    self.current_speed = dynamic_limit

        # Fisica anti colisions (Last Resort)
        distance_step = self.current_speed * (dt_minutes / 60.0)
        
        if dist_leader < float('inf'):
            #Distància de seguretat, la podriem augmentar
            SAFE_GAP_KM = 0.02 # 20 metres
            available_space = dist_leader - SAFE_GAP_KM
            
            if distance_step > available_space:
                distance_step = max(0.0, available_space)
                self.current_speed = 0.0 
                if self.is_training:
                    self.agent.update(state, action_idx, -500, state)

        self.distance_covered += distance_step
        self.sim_time += dt_minutes

        progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        TrafficManager.update_train_position(self.current_edge, self.id, progress_pct)

        new_delay = self.calculate_delay()
        
        # CÀLCUL DE RECOMPENSA FINAL
        reward = -1.0 
        reward += self.atp_penalty # Afegim el càstig de seguretat
        
        if abs(new_delay) > 2: reward -= 0.5 
        if action_idx != 1: reward -= 0.1 

        if self.distance_covered >= self.total_distance:
            if abs(new_delay) <= 2: reward += 100 
            else:
                reward += 10 
                reward -= min(50, abs(new_delay) * 2)
            self.arrive_at_station_logic()
        
        #actualitzacio de q table
        if self.is_training:
            # Actualitzem la memòria de distància per al pròxim frame calcul de tendència
            self.last_dist_leader = dist_leader
            
            new_state = None if self.finished else self._get_general_state()
            self.agent.update(state, action_idx, reward, new_state)

    def arrive_at_station_logic(self):
        """Lògica d'arribada: Aturar tren, registrar temps i iniciar espera."""
        self.current_speed = 0.0 
        self.distance_covered = self.total_distance 
        
        if self.target:
            self.arrival_logs[self.target.name] = self.sim_time

        self.is_waiting = True
        self.wait_timer = self.WAIT_TIME_MIN

    def depart_from_station(self):
        """Lògica de sortida: Canviar objectiu a la següent estació."""
        if self.current_edge:
            TrafficManager.remove_train_from_edge(self.current_edge, self.id)

        self.is_waiting = False
        self.current_node_idx += 1
        self.node = self.target
        
        if self.current_node_idx < len(self.route_nodes) - 1:
            self.target = self.route_nodes[self.current_node_idx + 1]
            self.setup_segment()
        else:
            # Fi de trajecte
            self.finished = True
            self.target = None
            TrafficManager.remove_train(self.id)

    def draw(self, screen):
        """Dibuixa el tren (cercle) interpolant la seva posició sobre la via."""
        if self.finished or not self.node or not self.target: return

        # Codi de colors semàfor segons retard
        if self.is_waiting:
            color = (255, 200, 0) # Groc: En estació
        else:
            delay = self.calculate_delay()
            if abs(delay) <= 2: color = (0, 255, 0) # Verd: A temps
            elif delay > 2:     color = (255, 0, 0) # Vermell: Retard
            else:               color = (0, 0, 255) # Blau: Avançat

        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        progress = max(0.0, min(1.0, self.distance_covered / self.total_distance))
        
        cur_x = start_x + dx * progress
        cur_y = start_y + dy * progress
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)

    def __repr__(self):
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"