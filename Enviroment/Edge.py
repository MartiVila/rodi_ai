from .EdgeType import EdgeType
import math
import pygame

class Edge:
    # Factor de conversió: Quants KM són 1 píxel de pantalla?
    # Ajusta-ho segons la mida del teu mapa. Ex: 0.1 -> 100px = 10km
    PIXELS_TO_KM = 0.05 

    def __init__(self, node1, node2, edge_type, track_id):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.track_id = track_id
        
        # Càlcul de distància física
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        self.pixel_length = math.sqrt(dx*dx + dy*dy)
        self.real_length_km = self.pixel_length * Edge.PIXELS_TO_KM
        
        self.update_properties()

    def update_properties(self):
        """Defineix la velocitat segons el tipus de via"""
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0
        elif self.edge_type == EdgeType.URBAN:
            self.max_speed_kmh = 85.0
        else: # OBSTACLE
            self.max_speed_kmh = 10.0 # Molt lent

        # Calculem quant triga IDEALMENT en hores i minuts
        # Temps (h) = Distancia (km) / Velocitat (km/h)
        if self.max_speed_kmh > 0:
            hours = self.real_length_km / self.max_speed_kmh
            self.expected_minutes = hours * 60
        else:
            self.expected_minutes = 999 # Infinit si està parat

        # Velocitat de visualització (simulació)
        # Això controla com de ràpid es mou el puntet a la pantalla (0.0 a 1.0)
        # Com més minuts reals, més lent ha de ser el progrés visual.
        # Factor arbitrari per visualització: 1 minut real = X frames
        self.vis_speed = 1.0 / (self.expected_minutes * 60) # Ex: 1 segon de simulació per minut real

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