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

        # Inicialitzem el primer segment
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
        # Nota: Conservem la velocitat actual (inèrcia) entre segments, 
        # tot i que normalment a l'estació és 0.

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
        Vector: (Segment_ID, %_Distància, Velocitat, Retard, Bloqueig)
        """
        # 1. Segment ID (On sóc?)
        if self.node and self.target:
            segment_id = self.agent.get_segment_id(self.node.name, self.target.name) 
        else:
            segment_id = "FI_TRAJECTE"

        # 2. Distància (Discretitzada en 50 passos)
        if self.total_distance > 0:
            pct = self.distance_covered / self.total_distance
            dist_state = int(pct * 50) 
            if dist_state > 49: dist_state = 49
        else:
            dist_state = 49
            
        # 3. Velocitat (Discretitzada de 10 en 10 km/h)
        speed_state = int(self.current_speed / 10.0)
        if speed_state > 12: speed_state = 12 # Max 120 km/h
        
        # 4. Retard (Discretitzat per l'Agent: Molt aviat, Bé, Tard, Molt Tard)
        delay = self.calculate_delay()
        diff_disc = self.agent.discretize_diff(int(delay))
        
        # 5. Alertes (Via bloquejada?)
        tid = self.current_edge.track_id if self.current_edge else 0
        is_blocked = TrafficManager.check_alert(self.node.name, self.target.name, tid)
        
        return (segment_id, dist_state, speed_state, diff_disc, is_blocked)

    """
    ############################################################################################
    ############################################################################################

    Mòdul de Física (Update Logic)

    ############################################################################################
    ############################################################################################
    """

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
        """Bucle principal de lògica del tren (1 cop per frame/step)."""
        if self.finished: return
        
        # A. GESTIÓ D'ESPERA A ESTACIÓ
        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                self.depart_from_station()
            return 

        # B. OBSERVACIÓ (RL)
        state = self._get_general_state()
        current_delay = self.calculate_delay()
        
        # C. DECISIÓ (ACT)
        # Per defecte, l'agent decideix
        action_idx = self.agent.action(state)
        
        # [Override] Mecanisme de seguretat per evitar bucles infinits si l'AI es torna boja
        # Si portem més de 60 minuts de retard, forcem acceleració (excepte si estem frenant per arribar)
        if current_delay > 60 and self.is_training:
             # Castiguem l'agent per haver arribat a aquesta situació
            self.agent.update(state, 2, -100, None)
            action_idx = 0 # Forçar Accelerar

        # [Override] Kickstart: Si està parat enmig del no-res, empenta aleatòria
        if self.current_speed < 1.0 and action_idx != 0:
            if random.random() < 0.5: action_idx = 0

        # [Override] Física de Seguretat: Frenada automàtica final de trajecte
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            # Corba de frenada per arribar a v=15 km/h a l'andana
            pct_dist = dist_remaining / self.BRAKING_DISTANCE_KM
            target_approach_speed = pct_dist * 80.0 + 15.0 
            
            if self.current_speed > target_approach_speed:
                self.current_speed = target_approach_speed
                action_idx = 2 # Marcam com a 'Frenar' per a l'aprenentatge

        # D. EXECUCIÓ FÍSICA
        if action_idx == 0: self.accelerate(dt_minutes) # ACCELERAR
        elif action_idx == 1: pass                      # MANTENIR
        elif action_idx == 2: self.brake(dt_minutes)    # FRENAR
            
        self.move(dt_minutes)
        self.sim_time += dt_minutes
        
        # Actualitzem posició al gestor global (per cues)
        progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        TrafficManager.update_train_position(self.current_edge, self.id, progress_pct)

        # E. CÀLCUL DE RECOMPENSA (LEARN)
        new_delay = self.calculate_delay()
        reward = -1.0 # Penalització base per existir (incentiva rapidesa)
        
        if abs(new_delay) > 2: reward -= 0.5 # Penalització extra per anar fora d'horari

        # He arribat a l'estació?
        if self.distance_covered >= self.total_distance:
            # Gran recompensa/càstig final
            if abs(new_delay) <= 2: 
                reward += 100 # Èxit total
            else:
                reward += 10 # Almenys has arribat
                reward -= min(50, abs(new_delay) * 2) # Però et resto punts pel retard
            
            self.arrive_at_station_logic()
        
        # F. ACTUALITZACIÓ Q-TABLE
        if self.is_training:
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

        # Càlcul vectorial de posició
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        # Normalització (Clamp) del progrés entre 0 i 1
        progress = max(0.0, min(1.0, self.distance_covered / self.total_distance))
        
        cur_x = start_x + dx * progress
        cur_y = start_y + dy * progress
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)

    def __repr__(self):
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"