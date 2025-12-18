import pygame
from .EdgeType import EdgeType

class TrainStatus:
    SENSE_RETARD = "ON TIME"     # < 15 min
    RETARD_MODERAT = "DELAYED"   # 15 - 30 min
    AVARIAT = "BROKEN"           # > 30 min

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

        self.setup_segment()

    def setup_segment(self):
        # (Codi existent per buscar aresta...)
        if self.target.id in self.node.neighbors:
            # Agafem les vies disponibles
            possible_edges = self.node.neighbors[self.target.id]
            # Deleguem a l'agent quina via agafar
            # (Aquí l'agent hauria d'aprendre a evitar OBSTACLE per no acumular retard)
            state = self.get_state(possible_edges)
            action = self.agent.choose_action(state)
            self.current_edge = possible_edges[action]
        else:
            self.finished = True

    def get_state(self, edges):
        # Retorna estat (similar al teu codi anterior però adaptat)
        s0 = edges[0].edge_type
        s1 = edges[1].edge_type
        return (self.node.id, self.target.id, s0, s1)

    def update(self, dt_minutes):
        """
        dt_minutes: quants minuts han passat a la simulació des de l'últim frame
        """
        if self.finished: return

        # 1. Actualitzem temps real del tren
        self.current_time_accumulated += dt_minutes
        
        # 2. Avancem posició (visual)
        # La velocitat visual depèn de si la via és ràpida o lenta (calculat a Edge)
        self.progress += self.current_edge.vis_speed 

        # 3. Comprovem estat de retard respecte a l'horari previst al TARGET
        target_schedule = self.schedule.get(self.target.id, 0)
        # Temps actual absolut = Hora sortida + Temps viatjat
        current_clock_time = self.start_time + self.current_time_accumulated
        
        self.delay_minutes = current_clock_time - target_schedule
        
        if self.delay_minutes < 15:
            self.status = TrainStatus.SENSE_RETARD
        elif self.delay_minutes < 30:
            self.status = TrainStatus.RETARD_MODERAT
        else:
            self.status = TrainStatus.AVARIAT

        # 4. Arribada a estació
        if self.progress >= 1.0:
            self.arrive_at_station()

    def arrive_at_station(self):
        self.progress = 0
        self.node = self.target
        self.route_index += 1
        
        # Recompensa a l'agent: Volem minimitzar el retard!
        # Reward negatiu gran si hi ha molt retard
        reward = -self.delay_minutes 
        # (Aquí cridaries self.agent.learn(...))

        if self.route_index < len(self.route) - 1:
            self.target = self.route[self.route_index + 1]
            self.setup_segment()
        else:
            self.finished = True

    def draw(self, screen):
        # (El teu codi de dibuix)
        # Pots canviar el color del tren segons self.status!
        color = (0, 255, 0) # Verd
        if self.status == TrainStatus.RETARD_MODERAT: color = (255, 165, 0) # Taronja
        if self.status == TrainStatus.AVARIAT: color = (255, 0, 0) # Vermell
        
        # Dibuixar cercle amb 'color'
        # ...