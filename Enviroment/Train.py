import pygame
import math
from .EdgeType import EdgeType # Import necessari per a get_state() 
class Train:
    def __init__(self, agent, start_node, target_node, available_edges):
        self.agent = agent
        self.node = start_node
        self.target = target_node
        self.edges = available_edges # [Edge_via_0, Edge_via_1]
        
        self.current_edge = None
        self.progress = 0
        self.travel_time = 0
        self.finished = False
        self.state_at_departure = None
        self.action_taken = None

        # --- LÒGICA DE DECISIÓ (COMUNICACIÓ AMB AGENT) ---
        self.decide_route()

    def get_state(self):
        """Construeix l'estat que veu l'agent: On soc, on vaig, com estan les vies"""
        status_0 = "OK" if self.edges[0].edge_type == EdgeType.NORMAL else "BAD"
        status_1 = "OK" if self.edges[1].edge_type == EdgeType.NORMAL else "BAD"
        return (self.node.id, self.target.id, status_0, status_1)

    def decide_route(self):
        # 1. Preguntar a l'agent
        self.state_at_departure = self.get_state()
        self.action_taken = self.agent.choose_action(self.state_at_departure)
        
        # 2. Executar decisió
        self.current_edge = self.edges[self.action_taken]
        
        # Debug
        # print(f"Tren a {self.node.name}: Tria via {self.action_taken} ({self.state_at_departure[2]}/{self.state_at_departure[3]})")

    def update(self):
        if self.finished: return

        # Avançar
        self.progress += self.current_edge.speed
        self.travel_time += 1 # Comptem frames com a temps

        if self.progress >= 1.0:
            self.progress = 1.0
            self.finished = True
            
            # --- FEEDBACK A L'AGENT (RECOMPENSA) ---
            # La recompensa és negativa (cost temporal). Volem minimitzar temps.
            # Normalitzem una mica per no tenir valors gegants (ex: -100 punts)
            reward = -self.travel_time 
            
            # L'estat següent seria estar al node destí (sense moure's encara)
            next_state = (self.target.id, None, "None", "None") 
            
            self.agent.learn(self.state_at_departure, self.action_taken, reward, next_state)
            
            # print(f"Tren arribat! Reward: {reward:.1f}. Q-Table updated.")

    def draw(self, screen):
        if not self.current_edge: return
        
        # Calcular posició amb l'offset de la via
        off = 3 if self.current_edge.track_id == 0 else -3
        dx = self.current_edge.node2.x - self.current_edge.node1.x
        dy = self.current_edge.node2.y - self.current_edge.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Inici i final desplaçats
        x1 = self.current_edge.node1.x + perp_x * off
        y1 = self.current_edge.node1.y + perp_y * off
        x2 = self.current_edge.node2.x + perp_x * off
        y2 = self.current_edge.node2.y + perp_y * off
        
        curr_x = x1 + (x2 - x1) * self.progress
        curr_y = y1 + (y2 - y1) * self.progress
        
        pygame.draw.circle(screen, (255, 200, 0), (int(curr_x), int(curr_y)), 4)