from .EdgeType import EdgeType
import math
import pygame

class Edge:
    PIXELS_TO_KM = 0.05 

    """
    Representa una connexió entre dos nodes amb un tipus d'aresta específic.
    """
    def __init__(self, node1, node2, edge_type, track_id):
        """
        Inicialitza una nova instància d'Edge.

        :param node1: Node d'inici de l'aresta
        :param node2: Node de final de l'aresta
        :param edge_type: Tipus d'aresta (EdgeType: Hi ha per ara NORMAL(0), URBAN(1), OBSTACLE(3))
        :param track_id: Identificador de la via (0 o 1)
        """
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
        """
        Actualitza les propietats de l'aresta basant-se en el seu tipus.
        """
        # 1. VELOCITAT FÍSICA MÀXIMA (La mantenim alta perquè el tren pugui recuperar)
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0 # El tren està limitat a 120, així que agafarà 120.
        else: # OBSTACLE
            self.max_speed_kmh = 10.0 
        
        # 2. VELOCITAT DE REFERÈNCIA PER HORARIS (Aquí posem els 90 km/h)
        if self.edge_type == EdgeType.NORMAL:
            reference_speed = 90.0 # <--- AQUESTA és la que mana a l'horari
        else:
            reference_speed = 10.0

        # Càlcul del temps esperat fent servir la REFERÈNCIA, no la màxima
        if reference_speed > 0:
            hours_min = self.real_length_km / reference_speed
            hours_scheduled = hours_min * 1.25  # Marge del 25%
            self.expected_minutes = hours_scheduled * 60
        else:
            self.expected_minutes = 999 

        # Vis_speed (només visual)
        if self.expected_minutes > 0:
            self.vis_speed = 1.0 / self.expected_minutes
        else:
            self.vis_speed = 1.0

    def draw(self, screen):
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        off =0
        #off = 3 if self.track_id == 0 else -3
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        start = (self.node1.x + perp_x * off, self.node1.y + perp_y * off)
        end = (self.node2.x + perp_x * off, self.node2.y + perp_y * off)
        pygame.draw.line(screen, color, start, end, width)