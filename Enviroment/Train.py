import pygame
import math
from .EdgeType import EdgeType

class Train:
    # Canvi: Ara rep 'route_nodes' (llista de Nodes) en lloc de start/target individuals
    def __init__(self, agent, route_nodes):
        self.agent = agent
        self.route = route_nodes 
        self.route_index = 0 # Estem a l'estació 0 de la ruta
        
        self.node = self.route[self.route_index]
        self.target = self.route[self.route_index + 1]
        
        self.edges = [] 
        self.current_edge = None
        self.progress = 0
        self.travel_time = 0
        self.finished = False
        
        # Inicialitzem el primer tram
        self.setup_segment()

    def setup_segment(self):
        """Prepara el tren per anar del node actual al següent target."""
        # Busquem les vies que connecten el node actual amb el target
        if self.target.id in self.node.neighbors:
            self.edges = self.node.neighbors[self.target.id]
            self.decide_route()
        else:
            # Error de seguretat si no hi ha connexió
            self.finished = True

    def get_state(self):
        status_0 = "OK" if self.edges[0].edge_type == EdgeType.NORMAL else "BAD"
        status_1 = "OK" if self.edges[1].edge_type == EdgeType.NORMAL else "BAD"
        return (self.node.id, self.target.id, status_0, status_1)

    def decide_route(self):
        self.state_at_departure = self.get_state()
        self.action_taken = self.agent.choose_action(self.state_at_departure)
        self.current_edge = self.edges[self.action_taken]

    def update(self):
        if self.finished: return

        self.progress += self.current_edge.speed
        self.travel_time += 1 

        if self.progress >= 1.0:
            # --- 1. Aprenentatge del tram completat ---
            reward = -self.travel_time 
            next_state = (self.target.id, "None", "None", "None") # Simplificació
            self.agent.learn(self.state_at_departure, self.action_taken, reward, next_state)

            # --- 2. Lògica de següent estació ---
            self.progress = 0
            self.travel_time = 0
            
            # Ens movem al node on acabem d'arribar
            self.node = self.target
            self.route_index += 1

            # Comprovem si queden més estacions a la ruta
            if self.route_index < len(self.route) - 1:
                self.target = self.route[self.route_index + 1]
                self.setup_segment() # Preparem el següent tram
            else:
                self.finished = True # Final de trajecte

    def draw(self, screen):
        # (El codi de draw es manté idèntic, ja que depèn de current_edge i progress)
        if not self.current_edge: return
        
        off = 3 if self.current_edge.track_id == 0 else -3
        dx = self.current_edge.node2.x - self.current_edge.node1.x
        dy = self.current_edge.node2.y - self.current_edge.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        
        x1 = self.current_edge.node1.x + perp_x * off
        y1 = self.current_edge.node1.y + perp_y * off
        x2 = self.current_edge.node2.x + perp_x * off
        y2 = self.current_edge.node2.y + perp_y * off
        
        curr_x = x1 + (x2 - x1) * self.progress
        curr_y = y1 + (y2 - y1) * self.progress
        
        pygame.draw.circle(screen, (255, 200, 0), (int(curr_x), int(curr_y)), 4)