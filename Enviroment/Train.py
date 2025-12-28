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

    def __init__(self, agent, route_nodes, schedule, start_time_sim, is_training=False, prefered_track=0):
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
        self.crashed = False
        self.current_edge = None
        
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
        self.setup_segment(preferred_track=prefered_track)

    def setup_segment(self, preferred_track=None):
        """
        Configura el tramo i REGISTRA IMMEDIATAMENT la posició per evitar Deadlocks.
        """
        if not self.target:
            self.finished = True
            return

        # Selecció de via (0 o 1)
        target_track = 0
        if preferred_track is not None:
            target_track = preferred_track
        elif getattr(self, 'current_edge', None):
             target_track = self.current_edge.track_id

        # Obtenim l'objecte via
        edge = TrafficManager.get_edge(self.node.name, self.target.name, target_track)
        
        # Fallback a via 0 si la preferida no existeix
        if not edge:
            edge = TrafficManager.get_edge(self.node.name, self.target.name, 0)

        if edge:
            self.current_edge = edge
            self.total_distance = edge.real_length_km
            self.max_speed_edge = edge.max_speed_kmh
            self.distance_covered = 0.0
            
            # --- FIX CRÍTIC: RESERVA IMMEDIATA ---
            # Registrem el tren al TrafficManager ARA MATEIX.
            # Així, si un altre tren consulta la via en aquest mateix 'tick',
            # ja veurà que està ocupada per nosaltres.
            TrafficManager.update_train_position(self.current_edge, self.id, 0.0)
            
        else:
            self.finished = True

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

    def _get_general_state(self, dist_leader, dist_oncoming):
        """
        Versió OPTIMIZADA.
        Rep els valors sensorials calculats prèviament per evitar recalcular-los.
        """
        
        # 1. Distancia al destino
        if self.total_distance > 0:
            pct = self.distance_covered / self.total_distance
            dist_state = int(pct * 10)
            if dist_state > 9: dist_state = 9
        else:
            dist_state = 9
        
        # 2. Velocidad
        speed_state = int(self.current_speed / 20.0)
        if speed_state > 6: speed_state = 6
        
        # 3. Visión Trasera (Líder) - Usem el valor passat per paràmetre
        if dist_leader > 3.0: proximity_state = 0   
        elif dist_leader > 1.0: proximity_state = 1 
        else: proximity_state = 2                   
        
        # 4. Tendencia
        diff = dist_leader - self.last_dist_leader
        if diff < -0.005: trend_state = 2   
        elif diff > 0.005: trend_state = 0  
        else: trend_state = 1               

        # 5. Retraso
        delay = self.calculate_delay()
        if delay < 1: diff_disc = 0    
        elif delay < 5: diff_disc = 1  
        else: diff_disc = 2            
        
        # 6. Riesgo Frontal - Usem el valor passat per paràmetre
        if dist_oncoming < 2.0: danger_state = 1 
        else: danger_state = 0                   

        # 7. Oportunidad de cambio de vía (SOLO SI HAY RAZÓN)
        can_switch = 0
        if self.current_edge:
            other_track = 1 if self.current_edge.track_id == 0 else 0
            other_edge = TrafficManager.get_edge(self.node.name, self.target.name, other_track)
            
            if other_edge:
                # Verificar que la otra vía está libre de trenes de frente
                dist_enemy_other = TrafficManager.check_head_on_collision(other_edge, 0.0)
                
                # SOLO permitir cambio si:
                # 1. La otra vía está libre de tráfico frontal (>5 km)
                # 2. Y HAY UN MOTIVO: líder cerca (<3 km) o peligro frontal (<5 km)
                if dist_enemy_other > 5.0:
                    # Hay motivo para cambiar?
                    has_reason = (dist_leader < 3.0) or (dist_oncoming < 5.0)
                    if has_reason:
                        can_switch = 1 

        return (dist_state, speed_state, proximity_state, trend_state, diff_disc, danger_state, can_switch)
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
        if self.current_speed < 1:
            self.current_speed = 1.0

    def brake(self, dt_minutes):
        self.current_speed -= self.BRAKING * dt_minutes
        if self.current_speed < 0:
            self.current_speed = 0

    def move(self, dt_minutes):
        # x = v * t
        distance_step = self.current_speed * (dt_minutes / 60.0)
        self.distance_covered += distance_step

    def update(self, dt_minutes):
        # [DEBUG BLOQUEIG] - Identificador únic per seguir aquest tren a la consola
        # Només imprimim si és el tren que està causant problemes (o un mostreig)
        debug = self.is_training and (self.id % 10 == 0) # Només 1 de cada 10 trens per no saturar
        
        if self.finished: return
        self.atp_penalty = 0.0 

        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                # 1. Identificamos hacia dónde vamos (siguiente tramo)
                next_idx = self.current_node_idx + 1
                
                # Si no es el final de trayecto...
                if next_idx < len(self.route_nodes) - 1:
                    next_u = self.route_nodes[next_idx]     # Estación actual (donde estamos parados)
                    next_v = self.route_nodes[next_idx + 1] # Siguiente estación destino
                    
                    # 2. PREGUNTAMOS AL TRAFFIC MANAGER: ¿HAY VÍA LIBRE?
                    safe_track = TrafficManager.get_safe_track(next_u.name, next_v.name)
                    
                    if safe_track is not None:
                        # ¡Luz verde! Salimos usando la vía segura encontrada
                        self.depart_from_station(preferred_track=safe_track)
                    else:
                        # ROJO: Todas las vías ocupadas.
                        # Nos quedamos en la estación (esperando 'apartados').
                        # Reiniciamos un pequeño timer para volver a comprobar en breve.
                        self.wait_timer = 0.5  # Comprobar de nuevo en 0.5 minutos simulados
                        
                else:
                    # Es la estación final, salimos para desaparecer del sistema
                    self.depart_from_station()
            return 

        # --- FASE 1: PERCEPCIÓ ---
        try:
            # 1. Calculem sensors UNA vegada
            dist_leader = self.get_vision_ahead()
            
            progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
            dist_oncoming = TrafficManager.check_head_on_collision(self.current_edge, progress_pct)
            
            # 2. Passem els valors a l'estat
            state = self._get_general_state(dist_leader, dist_oncoming)
            
        except Exception as e:
            print(f"!!! ERROR CRÍTIC EN PERCEPCIÓ (Tren {self.id}): {e}")
            self.finished = True
            return

        # --- FASE 2: DECISIÓ (On es penjava segons el traceback) ---
        try:
            # Si es penja aquí, és culpa de l'Agent.py o de l'estat passat
            # if debug: print(f"DEBUG: Tren {self.id} demanant acció per estat {state}...")
            
            action_idx = self.agent.action(state)
            
            # if debug: print(f"DEBUG: Tren {self.id} acció rebuda: {action_idx}")
            
        except Exception as e:
            print(f"!!! ERROR DINS AGENT.ACTION (Tren {self.id}): {e}")
            print(f"   Estat que ha provocat l'error: {state}")
            action_idx = 0 # Acció per defecte per no petar

        # --- AJUDES ENTRENAMENT ---
        current_delay = self.calculate_delay()
        if current_delay > 60 and self.is_training:
             self.agent.update(state, 2, -100, None) 
             action_idx = 0 
        if self.current_speed < 1.0 and action_idx != 0 and self.is_training:
            if random.random() < 0.5: action_idx = 0

        # Lògica d'aproximació a estació
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            pct_dist = dist_remaining / self.BRAKING_DISTANCE_KM
            target_approach_speed = pct_dist * 80.0 + 15.0 
            if self.current_speed > target_approach_speed:
                self.current_speed = target_approach_speed
                action_idx = 2 

        # --- FASE 3: ATP (SISTEMA DE SEGURETAT) ---
        override_speed_limit = float('inf')
        atp_intervention = False

        if dist_leader < 5.0:
            if dist_leader < 0.2:   override_speed_limit = 0.0 
            elif dist_leader < 1.0: override_speed_limit = 15.0
            elif dist_leader < 3.0: override_speed_limit = 45.0
            elif dist_leader < 5.0: override_speed_limit = 80.0

        if dist_oncoming < 2.0:
            override_speed_limit = 0.0 
            if self.current_speed > 5.0:
                 atp_intervention = True 

        current_limit = min(self.max_speed_edge, override_speed_limit)
        
        if self.current_speed > current_limit:
            self.current_speed -= (self.BRAKING * 1.5) * dt_minutes
            if self.current_speed < current_limit:
                self.current_speed = current_limit
            
            if self.is_training:
                if atp_intervention: 
                    self.atp_penalty = -500.0 
                elif override_speed_limit < self.max_speed_edge:
                    self.atp_penalty = -50.0 
                else:
                    self.atp_penalty = -10.0 

        # --- FASE 4: ACTUAR ---
        if action_idx == 0: 
            self.accelerate(dt_minutes)
        elif action_idx == 1: 
            pass
        elif action_idx == 2: 
            self.brake(dt_minutes)
        elif action_idx == 3: 
            # [PUNT DE RISC 3] Canvi de via (crida TrafficManager)
            if self.current_speed < 40.0: #and dist_oncoming > 2:
                self.atp_penalty += -2
                self.attempt_track_switch()
            #else:
                #if self.is_training: self.agent.update(state, 3, -50.0, state)
                #self.agent.update(state, 3, -50.0, state)

    

        if self.current_speed > current_limit: 
            self.current_speed = current_limit

        # --- FASE 5: FÍSICA ---
        distance_step = self.current_speed * (dt_minutes / 60.0)
        
        if dist_leader < float('inf'):
            SAFE_GAP_KM = 0.02
            available_space = dist_leader - SAFE_GAP_KM
            if distance_step > available_space:
                distance_step = max(0.0, available_space)
                self.current_speed = 0.0 

        self.distance_covered += distance_step
        TrafficManager.update_train_position(self.current_edge, self.id, self.distance_covered / self.total_distance)
        self.sim_time += dt_minutes

        # --- FASE 6: APRENENTATGE ---
        new_delay = self.calculate_delay()
        
        # [MODIFICACIÓ] Base reward
        reward = -0.1 + self.atp_penalty  # Reduïm la penalització base de -1.0 a -0.1 perquè no es desesperi 
        
        if self.current_speed > 5.0:
            # Recompensa positiva per estar en moviment (Incentiu vital)
            reward += 0.5 
        elif not self.is_waiting:
            # Penalització FORTA per estar parat a la via (més dolorós que arriscar-se)
            reward -= 2.0

        if abs(new_delay) > 2: reward -= 0.5 
        
        # PENALIZACIÓN FUERTE por cambio de vía innecesario
        # Solo queremos cambiar para adelantar/esquivar obstáculos
        if action_idx == 3:
            # Si había un motivo válido (líder cerca o peligro frontal), penalización menor
            has_valid_reason = (dist_leader < 3.0) or (dist_oncoming < 5.0)
            if has_valid_reason:
                reward -= 5.0  # Penalización moderada (cambio justificado pero costoso)
            else:
                reward -= 15.0  # Penalización ALTA por cambio innecesario 

        if self.distance_covered >= self.total_distance:
            if abs(new_delay) <= 2: reward += 100 
            else: reward += 10 - min(50, abs(new_delay) * 2)
            self.arrive_at_station_logic()
        
        #if self.is_training:
        self.last_dist_leader = dist_leader
        
        # --- CORRECCIÓ DE L'ERROR ---
        try:
            new_state = None
            if not self.finished:
                # 1. Recalculem els sensors per a la NOVA posició (s')
                #    És necessari perquè el tren s'ha mogut i l'entorn ha canviat.
                new_dist_leader = self.get_vision_ahead()
                
                new_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
                new_dist_oncoming = TrafficManager.check_head_on_collision(self.current_edge, new_pct)
                
                # 2. Passem els nous arguments obligatoris
                new_state = self._get_general_state(new_dist_leader, new_dist_oncoming)

            self.agent.update(state, action_idx, reward, new_state)
        except Exception as e:
            print(f"Error actualitzant Agent: {e}")



    def attempt_track_switch(self):
        """Intenta cambiar a la vía paralela SOLO si hay un motivo válido."""
        if not self.current_edge: return

        # VERIFICACIÓN PREVIA: ¿Hay razón para cambiar de vía?
        dist_leader = self.get_vision_ahead()
        pct_current = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        dist_oncoming = TrafficManager.check_head_on_collision(self.current_edge, pct_current)
        
        # Solo cambiar si hay un obstáculo real:
        # - Líder cerca (<3 km) que nos ralentiza
        # - Tren de frente cercano (<5 km) que requiere maniobra
        has_valid_reason = (dist_leader < 3.0) or (dist_oncoming < 5.0)
        
        if not has_valid_reason:
            return  # No cambiar de vía sin motivo

        current_track = self.current_edge.track_id
        target_track = 1 if current_track == 0 else 0
        
        # Solicitamos la vía paralela (track_id inverso)
        new_edge = TrafficManager.get_edge(self.node.name, self.target.name, target_track)
        
        if new_edge:
            # Calculamos el progreso actual para mantenerlo
            pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
            
            # CRÍTICO: Verificamos que la nueva vía no tenga un tren viniendo de cara
            # Debe mirar la MISMA VÍA FÍSICA (mismo track_id) en sentido contrario
            dist_enemy = TrafficManager.check_head_on_collision(new_edge, pct)
            
            # Solo cambiamos si hay un margen de seguridad suficiente
            if dist_enemy > 3.0:  # Aumentado a 3 km para mayor seguridad
                # 1. Quitamos el tren de la vía actual
                TrafficManager.remove_train_from_edge(self.current_edge, self.id)
                
                # 2. Actualizamos las referencias físicas del tren
                self.current_edge = new_edge
                self.max_speed_edge = new_edge.max_speed_kmh
                # La distancia cubierta 'distance_covered' se mantiene igual (teletransporte lateral)
                
                # 3. Registramos el tren en la nueva vía
                TrafficManager.update_train_position(self.current_edge, self.id, pct)
    def arrive_at_station_logic(self):
        """Lògica d'arribada: Aturar tren, registrar temps i iniciar espera."""
        self.current_speed = 0.0 
        self.distance_covered = self.total_distance 
        
        if self.target:
            self.arrival_logs[self.target.name] = self.sim_time

        self.is_waiting = True
        self.wait_timer = self.WAIT_TIME_MIN

    def depart_from_station(self, preferred_track=None):
        """Lògica de sortida: Canviar objectiu a la següent estació."""
        if self.current_edge:
            TrafficManager.remove_train_from_edge(self.current_edge, self.id)

        self.is_waiting = False
        self.current_node_idx += 1
        self.node = self.target
        
        if self.current_node_idx < len(self.route_nodes) - 1:
            self.target = self.route_nodes[self.current_node_idx + 1]
            self.setup_segment(preferred_track=preferred_track)
        else:
            # Fi de trajecte
            self.finished = True
            self.target = None
            TrafficManager.remove_train(self.id)

    def draw(self, screen):
        """Dibuixa el tren sobre la via corresponent (0 o 1) amb l'offset correcte."""
        if self.finished or not self.node or not self.target: return

        # ... (Codi de colors existent es manté igual) ...
        # (Copia aquí la teva lògica de colors existent)
        if getattr(self, 'crashed', False):
            color = (0, 0, 0)
        elif self.is_waiting:
            color = (255, 200, 0) 
        else:
            delay = self.calculate_delay()
            if abs(delay) <= 2: color = (0, 255, 0) 
            elif delay > 2:     color = (255, 0, 0) 
            else:               color = (0, 0, 255) 

        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        # Progrés lineal
        progress = max(0.0, min(1.0, self.distance_covered / self.total_distance))
        cur_x = start_x + dx * progress
        cur_y = start_y + dy * progress

        length = math.sqrt(dx*dx + dy*dy)
        
        current_track = 0
        if self.current_edge:
            current_track = self.current_edge.track_id
            
        # [CORRECCIÓ VISUAL DEFINITIVA]
        # Detectem si estem anant en direcció "Normal" (Anada) o "Inversa" (Tornada)
        # Això és necessari perquè l'offset perpendicular canvia de costat segons el sentit.
        
        # Assumim 'Anada' si el parell (Origen, Destí) està definit a Datas
        is_anada = (self.node.name, self.target.name) in Datas.R1_CONNECTIONS
        
        if current_track == 0:
            # Via Interior (0)
            # Si anem 'Anada': Offset positiu (6.0) -> Baixa (Dreta)
            # Si anem 'Tornada': Offset negatiu (-6.0) -> Baixa (Dreta respecte a l'Anada)
            offset_dist = 6.0 if is_anada else -6.0
        else:
            # Via Exterior (1)
            # Si anem 'Anada' (Overtaking): Offset negatiu (-10.0) -> Puja (Esquerra)
            # Si anem 'Tornada' (Normal Track 1): Offset positiu (10.0) -> Puja (Esquerra respecte a l'Anada)
            offset_dist = -10.0 if is_anada else 10.0
        
        if length > 0:
            # El vector perpendicular posa el tren exactament sobre la línia dibuixada
            off_x = (-dy / length) * offset_dist
            off_y = (dx / length) * offset_dist
            
            cur_x += off_x
            cur_y += off_y

        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 4)

    def __repr__(self):
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"