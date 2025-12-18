from . import EdgeType
import math
import pygame

class Edge:
    def __init__(self, node1, node2, edge_type, duration, track_id):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.base_duration = duration
        self.track_id = track_id  # 0 o 1 (per identificar via paral·lela)
        self.update_properties()

    def update_properties(self):
        # Si està trencada, triga 5 vegades més
        factor = 1.0 if self.edge_type == EdgeType.NORMAL else 5.0
        self.current_duration = self.base_duration * factor
        # Velocitat de visualització (progrés per frame)
        self.speed = 1.0 / max(self.current_duration, 1)

    def draw(self, screen):
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        
        # Càlcul d'offset per dibuixar les dues vies paral·leles sense solapar-se
        off = 3 if self.track_id == 0 else -3
        
        # Vector direcció
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        
        # Vector perpendicular unitari (-dy, dx)
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Punts desplaçats
        start = (self.node1.x + perp_x * off, self.node1.y + perp_y * off)
        end = (self.node2.x + perp_x * off, self.node2.y + perp_y * off)
        
        pygame.draw.line(screen, color, start, end, width)