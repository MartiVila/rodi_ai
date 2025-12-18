import pygame
from .EdgeType import EdgeType

class TrainStatus:
    SENSE_RETARD = "ON TIME"     # < 5 min
    RETARD_MODERAT = "DELAYED"   # 5 - 15 min
    AVARIAT = "BROKEN"           # > 15 min (He ajustat els llindars per ser més realistes)

class Train:
    def __init__(self, agent, route_nodes, scheduled_times, start_time_sim):
        self.agent = agent
        self.route = route_nodes
        self.schedule = scheduled_times # Dict {node_id: minut_arribada_teoric}
        self.start_time = start_time_sim # Minut de sortida global
        
        self.route_index = 0
        self.node = self.route[0]
        self.target = self.route[1]
        
        self.current_time_accumulated = 0 # Temps que porta viatjant el tren
        self.status = TrainStatus.SENSE_RETARD
        self.delay_minutes = 0
        
        # Variables d'estat
        self.finished = False
        self.progress = 0.0
        self.current_edge = None

        self.setup_segment()

    def setup_segment(self):
        """Prepara el següent tram del viatge."""
        if self.target.id in self.node.neighbors:
            possible_edges = self.node.neighbors[self.target.id]
            
            # Agent decideix via (0 o 1)
            state = self.get_state(possible_edges)
            action = self.agent.choose_action(state)
            
            self.current_edge = possible_edges[action]
            self.progress = 0.0
        else:
            self.finished = True

    def get_state(self, edges):
        s0 = edges[0].edge_type
        s1 = edges[1].edge_type
        return (self.node.id, self.target.id, s0, s1)

    def update(self, dt_minutes):
        """
        dt_minutes: minuts de simulació que han passat en aquest frame.
        """
        if self.finished: return

        # 1. El temps passa igual per a tothom
        self.current_time_accumulated += dt_minutes
        
        # 2. Avancem posició visual
        # vis_speed ara és (fracció de via / minut). Ex: 0.2 (tarda 5 minuts)
        # 0.2 * 1 minut = 0.2 progrés. Correcte.
        if self.current_edge:
             self.progress += self.current_edge.vis_speed * dt_minutes
        
        # 3. Calculem el retard actual
        target_schedule = self.schedule.get(self.target.id, 0)
        current_clock_time = self.start_time + self.current_time_accumulated
        
        # Retard = Hora Actual - Hora Prevista
        self.delay_minutes = max(0, current_clock_time - target_schedule)
        
        # Actualitzem l'estat textual
        if self.delay_minutes < 5:
            self.status = TrainStatus.SENSE_RETARD
        elif self.delay_minutes < 15:
            self.status = TrainStatus.RETARD_MODERAT
        else:
            self.status = TrainStatus.AVARIAT

        # 4. Arribada a estació
        if self.progress >= 1.0:
            self.arrive_at_station()

    def arrive_at_station(self):
        # --- NOVA LÒGICA DE RECOMPENSA [PROFESSOR FIX] ---
        
        # 1. Base: Recompensa positiva per arribar (objectiu complert)
        reward = 0 

        # 2. Penalitzacions i Bonus segons la magnitud del retard
        if self.delay_minutes <= 1:
            # CAS ÒPTIM: Puntualitat perfecta o marge menyspreable
            # Donem un reforç positiu fort per incentivar aquest comportament.
            reward += 20 
        
        elif self.delay_minutes < 5:
            # RETARD LLEU (SENSE_RETARD): < 5 min
            # Penalització lineal suau. Un retard de 4 minuts no és greu.
            reward -= (self.delay_minutes * 2)
            
        elif self.delay_minutes < 15:
            # RETARD MODERAT: 5 - 15 min
            # Penalització quadràtica. Volem que l'agent "tingui por" d'entrar aquí.
            # Exemple: 10 minuts -> -100 punts
            reward -= (self.delay_minutes ** 2)
            
        else:
            # RETARD SEVER (AVARIAT): > 15 min
            # Penalització massiva i lineal agressiva addicional.
            reward -= 500 + (self.delay_minutes * 10)

        # 3. Aprenentatge Q-Learning (Codi original intacte)
        possible_edges = self.node.neighbors[self.target.id]
        state = self.get_state(possible_edges)
        action = self.current_edge.track_id 
        next_state = state 
        
        self.agent.learn(state, action, reward, next_state)

        # Següent parada (Codi original intacte)
        self.node = self.target
        self.route_index += 1
        
        if self.route_index < len(self.route) - 1:
            self.target = self.route[self.route_index + 1]
            self.setup_segment()
        else:
            self.finished = True

    def draw(self, screen):
        if self.finished: return

        color = (0, 200, 0) 
        if self.status == TrainStatus.RETARD_MODERAT: color = (230, 140, 0) 
        if self.status == TrainStatus.AVARIAT: color = (200, 0, 0) 
        
        # Lògica de dibuix (Interpolar posició)
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        off = 5 if self.current_edge.track_id == 0 else -5
        
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Assegurem que el progrés no visualitzi més enllà de l'1.0 abans del canvi de segment
        safe_progress = min(1.0, self.progress)
        
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)