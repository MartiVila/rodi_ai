from .EdgeType import EdgeType
import math
import pygame

class Edge:
    PIXELS_TO_KM = 0.05 

    def __init__(self, node1, node2, edge_type, track_id):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.track_id = track_id
        
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        self.pixel_length = math.sqrt(dx*dx + dy*dy)
        self.real_length_km = self.pixel_length * Edge.PIXELS_TO_KM
        
        self.update_properties()

    def update_properties(self):
        """Defineix la velocitat i l'horari amb el marge de temps sol·licitat."""
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0
        elif self.edge_type == EdgeType.URBAN:
            self.max_speed_kmh = 85.0
        else: # OBSTACLE
            self.max_speed_kmh = 10.0 

        # Càlcul del temps esperat (Schedule)
        # Regla: Temps mínim a màxima velocitat + 1/4 (25%) de marge extra.
        if self.max_speed_kmh > 0:
            hours_min = self.real_length_km / self.max_speed_kmh
            hours_scheduled = hours_min * 1.25  # Afegeix 25% de temps
            self.expected_minutes = hours_scheduled * 60
        else:
            self.expected_minutes = 999 

        # Vis_speed es fa servir per debug o moviment simple, però ara el tren
        # calcularà la seva pròpia velocitat, així que això és secundari.
        if self.expected_minutes > 0:
            self.vis_speed = 1.0 / self.expected_minutes
        else:
            self.vis_speed = 1.0

    def draw(self, screen):
        # (El mètode draw es manté igual que l'original)
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        off = 3 if self.track_id == 0 else -3
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        start = (self.node1.x + perp_x * off, self.node1.y + perp_y * off)
        end = (self.node2.x + perp_x * off, self.node2.y + perp_y * off)
        pygame.draw.line(screen, color, start, end, width)