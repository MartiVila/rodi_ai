from .EdgeType import EdgeType
import math
import pygame

class Edge:
    """
    Un edge es la connexio unidireccional entre dos nodes. sen crearan dos un per cada sentit per cada via fisica
    Conté la lògica de distàncies i límits de velocitat.
    """
    
    #conversió de quan valen pixels a km reals
    PIXELS_TO_KM = 0.05 

    def __init__(self, node1, node2, edge_type, track_id):
        """
        node1: Node origen.
        node2: Node destí.
        edge_type: dos tipus, normal es perf, obstacle esta en vermell
        track_id: ID de la via (0: anada, 1: tornada) per dibuixar amb decalatge.
        """
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.track_id = track_id
        
        #vector entre nodes per obtenir longitud en píxels
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        self.pixel_length = math.sqrt(dx*dx + dy*dy)
        
        #distancia real en km del tram
        self.real_length_km = self.pixel_length * Edge.PIXELS_TO_KM
        
        #inicialitza velocitats i temps esperats segons l'estat de la via
        self.update_properties()

    def update_properties(self):
        """
        Recalcula les velocitats màximes i els temps esperats segons el tipus de via.
        Es crida quan una via es trenca (OBSTACLE) o es repara (NORMAL).
        """
        #velocitat física usada per simular el temps real del tren
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0 
        else: 
            self.max_speed_kmh = 10.0
        
        #velocitat teòrica per càlcul de temps programat (amb marge extra per parades i acceleracions)
        reference_speed = 90.0 if self.edge_type == EdgeType.NORMAL else 10.0

        if reference_speed > 0:
            hours_min = self.real_length_km / reference_speed
            #marge incrementat un 60% per apropar-se a horaris realistes
            hours_scheduled = hours_min * 1.60
            self.expected_minutes = hours_scheduled * 60
        else:
            self.expected_minutes = 999.0

    def draw(self, screen):
        """
        Dibuixa la línia tenint en compte el Track ID per separar visualment les vies.
        gris normal, vermell obstacle
        """
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        
        #vectors per calcular l'offset que separa les dues vies en pantalla
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        length = math.sqrt(dx*dx + dy*dy)
        
        if self.track_id == 0:
            offset_dist = 6.0 
        else:
            offset_dist = 8.0
        
        off_x, off_y = 0, 0
        if length > 0:
            off_x = (-dy / length) * offset_dist
            off_y = (dx / length) * offset_dist

        start = (self.node1.x + off_x, self.node1.y + off_y)
        end = (self.node2.x + off_x, self.node2.y + off_y)
        
        pygame.draw.line(screen, color, start, end, width)