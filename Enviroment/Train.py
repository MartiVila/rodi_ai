import pygame
import math
import random
from Enviroment.Datas import Datas
from Enviroment.TrafficManager import TrafficManager 
from Enviroment.EdgeType import EdgeType

class Train:
    """
    Representa un tren individiaul, amb la seva lògica de moviment, estats i interacció amb l'agent d'IA.
    """
    
    ACCELERATION = 120.0   #l'acceleració del tren
    BRAKING = 200.0         # Frenada forta
    MAX_SPEED_TRAIN = 140.0 #Velocitat màxima dels trens
    BRAKING_DISTANCE_KM = 0.05 #Distància de seguretat per frenar davant estació

    def __init__(self, agent, route_nodes, schedule, start_time_sim, is_training=False, prefered_track=0):
        """
        agent: Referència al QLearningAgent compartit.
        route_nodes: Llista d'objectes Node que formen la ruta.
        schedule: Diccionari {node_id: temps_arribada_previst}.
        start_time_sim: Hora d'inici de la simulació.
        """
        self.agent = agent
        self.route_nodes = route_nodes
        self.schedule = schedule
        self.is_training = is_training

        self.id = id(self)
        self.finished = False
        self.crashed = False
        self.current_edge = None
        
        #navegació per la ruta
        self.current_node_idx = 0
        self.node = self.route_nodes[0] #Estació actual/origen
        self.target = self.route_nodes[1] if len(route_nodes) > 1 else None #Pròxima estació
        
        #Logs per l'informe final
        self.arrival_logs = {} 
        if self.node:
            self.arrival_logs[self.node.name] = start_time_sim

        #Estat del moviment
        self.current_speed = 0.0
        self.distance_covered = 0.0
        self.total_distance = 1.0 
        self.max_speed_edge = 90.0 
        
        self.sim_time = start_time_sim
        
        #Estat de la parada
        self.is_waiting = False    
        self.wait_timer = 0.0      
        self.WAIT_TIME_MIN = Datas.STOP_STA_TIME   
        
        self.last_dist_leader = float('inf')
        #Penalty acumulatiu per ús excesiu de ATP
        #ATP ha de ser només en cas d'emergència
        self.atp_penalty = 0.0

        #Inicialitzem el primer segment
        self.setup_segment(preferred_track=prefered_track)

    def setup_segment(self, preferred_track=None):
        """
        configurem el tren i registrem el segment on estem
        """
        if not self.target:
            self.finished = True
            return

        #via o 0 o 1, dreta o esquerra
        target_track = 0
        if preferred_track is not None:
            target_track = preferred_track
        elif getattr(self, 'current_edge', None):
             target_track = self.current_edge.track_id

        #via "preferida"
        edge = TrafficManager.get_edge(self.node.name, self.target.name, target_track)

        #en el cas que la via que tenim com a preferida hem de buscar una alternativa
        if edge and getattr(edge, 'edge_type', None) == EdgeType.OBSTACLE:
            safe = TrafficManager.get_safe_track(self.node.name, self.target.name)
            if safe is not None:
                edge = TrafficManager.get_edge(self.node.name, self.target.name, safe)
            else:
                #qualsevol via no obstacle
                other0 = TrafficManager.get_edge(self.node.name, self.target.name, 0)
                other1 = TrafficManager.get_edge(self.node.name, self.target.name, 1)
                edge = None
                if other0 and getattr(other0, 'edge_type', None) != EdgeType.OBSTACLE:
                    edge = other0
                elif other1 and getattr(other1, 'edge_type', None) != EdgeType.OBSTACLE:
                    edge = other1

        #Fallback a via 0 si no hi ha elecció i no és obstacle
        if not edge:
            edge = TrafficManager.get_edge(self.node.name, self.target.name, 0)
            if edge and getattr(edge, 'edge_type', None) == EdgeType.OBSTACLE:
                edge = None

        if edge:
            self.current_edge = edge
            self.total_distance = edge.real_length_km
            self.max_speed_edge = edge.max_speed_kmh
            self.distance_covered = 0.0
            
            #Registrem el tren al TrafficManager ARA MATEIX.
            #Així, si un altre tren consulta la via en aquest mateix 'tick',
            #ja veurà que està ocupada per nosaltres.
            TrafficManager.update_train_position(self.current_edge, self.id, 0.0)
            
        else:
            self.finished = True

    '''
    Estats i recompenses
    '''

    def calculate_delay(self):
        """
        Calcula el retard projectat a la pròxima estació.
        Retard = (Hora Actual + Temps Estimat Viatge) - Hora Prevista Horari
        """
        if not self.target: return 0
        expected_arrival = self.schedule.get(self.target.id)
        if expected_arrival is None: return 0
        
        remaining_dist_km = self.total_distance - self.distance_covered
        
        #calcula la distànciamitjana per preveure el delay
        projected_speed = max(self.current_speed, self.max_speed_edge * 0.9)
        if projected_speed <= 10: projected_speed = 60.0 #accelerem aviat

        time_needed_min = (remaining_dist_km / projected_speed) * 60
        projected_arrival_time = self.sim_time + time_needed_min
        
        return projected_arrival_time - expected_arrival

    def _get_general_state(self, dist_leader, dist_oncoming):
        """
        Rep els valors calculats prèviament per evitar recalcular-los.
        """
        #distancia fins el desti
        if self.total_distance > 0:
            pct = self.distance_covered / self.total_distance
            dist_state = int(pct * 10)
            if dist_state > 9: dist_state = 9
        else:
            dist_state = 9
        
        #la velocitat
        speed_state = int(self.current_speed / 20.0)
        if speed_state > 6: speed_state = 6
        
        #tambe volem mirar els trens de darrera
        if dist_leader > 3.0: proximity_state = 0   
        elif dist_leader > 1.0: proximity_state = 1 
        else: proximity_state = 2                   
        
        diff = dist_leader - self.last_dist_leader
        if diff < -0.005: trend_state = 2   
        elif diff > 0.005: trend_state = 0  
        else: trend_state = 1               

        #el retras que poguem portar
        delay = self.calculate_delay()
        if delay < 1: diff_disc = 0    
        elif delay < 5: diff_disc = 1  
        else: diff_disc = 2            
        
        #si el tren se situa a menys de 2km estem en perill
        #etsat binari de perill o no 
        if dist_oncoming < 2.0: danger_state = 1 
        else: danger_state = 0                   

        #mirem si podem canviar de via
        can_switch = 0
        if self.current_edge:
            #other edge és la via paralela
            other_track = 1 if self.current_edge.track_id == 0 else 0
            other_edge = TrafficManager.get_edge(self.node.name, self.target.name, other_track)
            
            if other_edge:
                #verifiquem que la via on cambiem estigui lliure de trens en sentit contrari
                dist_enemy_other = TrafficManager.check_head_on_collision(other_edge, 0.0)
                
                #nomes cambiem si 
                #l'altre via esta lliure de sentit contrari
                #Hi ha un motiu com un perill o obstacle 
                if dist_enemy_other > 5.0:
                    has_reason = (dist_leader < 3.0) or (dist_oncoming < 5.0)
                    if has_reason:
                        can_switch = 1 

        return (dist_state, speed_state, proximity_state, trend_state, diff_disc, danger_state, can_switch)
    '''
    lògica de moviment
    '''

    def get_vision_ahead(self):
        """
        evitem punt secundari mirant a la següent via si estem a prop del final
        Retorna la distància al líder en la via actual o la suma de distàncies
        """
        #via actual
        dist = TrafficManager.get_distance_to_leader(self.current_edge, self.id)
        
        #Si no hi ha ningú davant (infinit) I estem a prop del final (>90% recorregut),
        #mirem la següent via.
        if dist == float('inf') and self.distance_covered > (self.total_distance * 0.9):
            #Identificar següent tram
            if self.current_node_idx + 1 < len(self.route_nodes) - 1:
                next_u = self.route_nodes[self.current_node_idx + 1] #l meu target actual
                next_v = self.route_nodes[self.current_node_idx + 2] #El següent al target
                
                next_edge = TrafficManager.get_edge(next_u.name, next_v.name)
                if next_edge:
                    #Busquem l'últim tren de la següent via
                    #La llista està ordenada per progrés descendent el primer tren es el mes avançat
                    trains_next = TrafficManager._train_positions.get(next_edge, [])
                    if trains_next:
                        #últim de la llista és el que té menys progrés
                        leader_id, leader_prog = trains_next[-1] 
                        
                        dist_to_end_of_current = self.total_distance - self.distance_covered
                        dist_of_leader_in_next = leader_prog * next_edge.real_length_km
                        
                        return dist_to_end_of_current + dist_of_leader_in_next

        return dist

    def accelerate(self, dt_minutes):
        self.current_speed += self.ACCELERATION * dt_minutes
        #La velocitat del tren o la de la via, la que sigui menor
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
        distance_step = self.current_speed * (dt_minutes / 60.0)
        self.distance_covered += distance_step

    def update(self, dt_minutes):
        if self.finished: return
        self.atp_penalty = 0.0 

        #logica de parada a estació, o apartadero
        if self.is_waiting:
            self.sim_time += dt_minutes
            self.wait_timer -= dt_minutes
            
            if self.wait_timer <= 0:
                next_idx = self.current_node_idx + 1
                if next_idx < len(self.route_nodes) - 1:
                    next_u, next_v = self.route_nodes[next_idx], self.route_nodes[next_idx + 1]
                    safe_track = TrafficManager.get_safe_track(next_u.name, next_v.name)
                    
                    if safe_track is not None:
                        target_edge = TrafficManager.get_edge(next_u.name, next_v.name, safe_track)
                        if target_edge and TrafficManager.check_head_on_collision(target_edge, 0.0) < 10.0:
                            self.wait_timer = 0.5; return 
                        
                        self.depart_from_station(preferred_track=safe_track)
                    else: 
                        self.wait_timer = 0.5 
                else: 
                    self.depart_from_station() 
            return 

        #control d'accés a l'estació
        dist_remaining = self.total_distance - self.distance_covered
        if dist_remaining < 0.05 and self.target and not self.target.has_capacity():
            self.current_speed = 0.0
            self.sim_time += dt_minutes
            return

        #percepció
        try:
            dist_leader = self.get_vision_ahead()
            pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
            dist_oncoming = TrafficManager.check_head_on_collision(self.current_edge, pct)
            state = self._get_general_state(dist_leader, dist_oncoming)
        except: self.finished = True; return

        #decisió de l'agent
        try: action_idx = self.agent.action(state)
        except: action_idx = 0 
        
        #ajude per un millor entrenament
        if self.current_speed < 1.0 and action_idx != 0 and self.is_training:
            if random.random() < 0.2: action_idx = 0 

        #frenada automatica en entrar a l'estació
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            target_approach = (dist_remaining / self.BRAKING_DISTANCE_KM) * 80.0 + 40.0 
            if self.current_speed > target_approach:
                self.current_speed = target_approach
                action_idx = 2 

        #sistema ATP bàsic
        override_speed = float('inf')

        #una petita protecció extra
        if dist_oncoming < 3.0:
            override_speed = 0.0
            if self.current_speed > 10: self.atp_penalty = -100
        
        elif dist_leader < 3.0: 
            #mirem si el 1r tren esta a la mateixa via o a la següent
            #Si get_distance_to_leader retorna infinit, és que el primer tren no és a la via actual,
            #per tant, el que hem vist a 'dist_leader' és algú a la següent estació.
            dist_same_track = TrafficManager.get_distance_to_leader(self.current_edge, self.id)
            
            if dist_same_track == float('inf'):
                #lider a la seguent estacio 
                #deixem passa el tren
                if dist_leader < 0.1: override_speed = 15.0
                else: override_speed = self.max_speed_edge #Via lliure per apropar-se
            else:
                #lider a la mateixa via per tant frenem més
                if dist_leader < 0.2: override_speed = 0.0
                elif dist_leader < 1.0: override_speed = 30.0
                elif dist_leader < 2.0: override_speed = 60.0
                else: override_speed = 100.0

        current_limit = min(self.max_speed_edge, override_speed)
        
        if self.current_speed > current_limit:
            self.current_speed -= (self.BRAKING * 2.0) * dt_minutes 
            if self.current_speed < current_limit: self.current_speed = current_limit
            if self.is_training: self.atp_penalty -= 5.0

        if action_idx == 0: self.accelerate(dt_minutes)
        elif action_idx == 1: pass 
        elif action_idx == 2: 
            #només es pot frenar si hi ha un motiu real
            has_reason = (
                dist_remaining < self.BRAKING_DISTANCE_KM * 2.0 or #Arribant a estació
                self.current_speed > self.max_speed_edge or        #Massa ràpid
                dist_leader < 5.0 or                               #Trànsit davant
                dist_oncoming < 5.0                                #Trànsit de cara
            )
            if has_reason:
                self.brake(dt_minutes)
            else:
                pass 

        elif action_idx == 3: 
            if not self.attempt_track_switch():
                self.atp_penalty -= 2.0 
                self.accelerate(dt_minutes) 

        if self.current_speed > current_limit: self.current_speed = current_limit

        dist_step = self.current_speed * (dt_minutes / 60.0)
        
        if dist_leader < float('inf'):
            avail = dist_leader - 0.01 
            if dist_step > avail:
                dist_step = max(0.0, avail)
                self.current_speed = 0.0 

        self.distance_covered += dist_step
        TrafficManager.update_train_position(self.current_edge, self.id, self.distance_covered/self.total_distance)
        self.sim_time += dt_minutes

        #recompenses i transició d'estat
        new_delay = self.calculate_delay()
        reward = -0.1 + self.atp_penalty 
        if self.current_speed > 5.0: reward += 0.5 
        elif not self.is_waiting: reward -= 4.0 
        if new_delay > 1.0: reward -= (new_delay * 0.5) 

        prev_delay = getattr(self, 'last_known_delay', new_delay)
        if new_delay < prev_delay: reward += 1.0
        self.last_known_delay = new_delay

        if self.distance_covered >= self.total_distance:
            if abs(new_delay) <= 2: reward += 100 
            else: reward += 10 - min(50, abs(new_delay) * 2)
            self.arrive_at_station_logic()
        
        self.last_dist_leader = dist_leader
        try:
            if not self.finished:
                ns = self._get_general_state(self.get_vision_ahead(), TrafficManager.check_head_on_collision(self.current_edge, self.distance_covered/self.total_distance))
                self.agent.update(state, action_idx, reward, ns)
        except: pass

    def attempt_track_switch(self):
        """
        Intenta canviar a la via paral·lela.
        Retorna True si ha canviat, False si no ha pogut (perquè l'update sàpiga què fer).
        """
        if not self.current_edge: return False

        #nomes pots canviar a l'estació
        #si ja hem passat 300m no es pot canviar
        if self.distance_covered > 0.3:
            return False

        #comprovem si hi ha rao per canviar
        dist_leader = self.get_vision_ahead()
        pct_current = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        dist_oncoming = TrafficManager.check_head_on_collision(self.current_edge, pct_current)
        
        has_valid_reason = (dist_leader < 3.0) or (dist_oncoming < 5.0)
        if not has_valid_reason:
            return False

        #canvi en si mateix
        current_track = self.current_edge.track_id
        target_track = 1 if current_track == 0 else 0
        new_edge = TrafficManager.get_edge(self.node.name, self.target.name, target_track)
        
        if new_edge:
            pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
            dist_enemy = TrafficManager.check_head_on_collision(new_edge, pct)
            
            #marge de seguretat
            if dist_enemy > 3.0: 
                TrafficManager.remove_train_from_edge(self.current_edge, self.id)
                self.current_edge = new_edge
                self.max_speed_edge = new_edge.max_speed_kmh
                TrafficManager.update_train_position(self.current_edge, self.id, pct)
                return True

        return False
        
    def arrive_at_station_logic(self):
        """
        lògica quan el tren arriba a l'estació
        aturar tren.
        ocupar slot a l'estació.
        calcular si anem d'hora i ajustar el temps d'espera
        """
        self.current_speed = 0.0 
        self.distance_covered = self.total_distance 
        
        #ocupar espai estaciuo
        if self.target:
            self.target.enter_station()
            self.arrival_logs[self.target.name] = self.sim_time

            #recalucalr si hem desperar per anivell si anessim d´hora
            scheduled_arrival = self.schedule.get(self.target.id)
            
            wait_time_needed = self.WAIT_TIME_MIN #parada tecnica
            
            if scheduled_arrival is not None:
                #si anessim d'hora hem d'esperar més
                delay = self.sim_time - scheduled_arrival
                
                if delay < 0:
                    early_minutes = abs(delay)
                    wait_time_needed += early_minutes
                   
            self.wait_timer = wait_time_needed
        else:
            self.wait_timer = self.WAIT_TIME_MIN

        self.is_waiting = True

    def depart_from_station(self, preferred_track=None):
        """
        l'ògica de la soprtida de l'estació
        alliberar slot a l'estació
        preparar el següent segment
        """
        #allibera espai estació
        if self.target:
            self.target.exit_station()

        if self.current_edge:
            TrafficManager.remove_train_from_edge(self.current_edge, self.id)

        self.is_waiting = False
        self.current_node_idx += 1
        
        #origen es don hem sortit
        self.node = self.target
        
        if self.current_node_idx < len(self.route_nodes) - 1:
            self.target = self.route_nodes[self.current_node_idx + 1]
            self.setup_segment(preferred_track=preferred_track)
        else:
            #fi del trajecte
            self.finished = True
            self.target = None
            TrafficManager.remove_train(self.id)

    def draw(self, screen):
        if self.finished or not self.node or not self.target: return

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
        
        progress = max(0.0, min(1.0, self.distance_covered / self.total_distance))
        cur_x = start_x + dx * progress
        cur_y = start_y + dy * progress

        length = math.sqrt(dx*dx + dy*dy)
        
        current_track = 0
        if self.current_edge:
            current_track = self.current_edge.track_id

        is_anada = (self.node.name, self.target.name) in Datas.R1_CONNECTIONS
        
        if current_track == 0:

            offset_dist = 6.0 if is_anada else -6.0
        else:

            offset_dist = -10.0 if is_anada else 10.0
        
        if length > 0:

            off_x = (-dy / length) * offset_dist
            off_y = (dx / length) * offset_dist
            
            cur_x += off_x
            cur_y += off_y

        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 4)

    def __repr__(self):
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"