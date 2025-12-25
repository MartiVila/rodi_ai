from .EdgeType import EdgeType
import math
import pygame

class Edge:
    """
    Representa una connexió física (via) entre dos Nodes.
    Conté la lògica de distàncies i límits de velocitat.
    """
    
    # Factor de conversió: Quants km reals representa 1 píxel de pantalla
    PIXELS_TO_KM = 0.05 

    def __init__(self, node1, node2, edge_type, track_id):
        """
        :param node1: Node origen.
        :param node2: Node destí.
        :param edge_type: Tipus (NORMAL/OBSTACLE) que defineix la velocitat.
        :param track_id: ID de la via (0: anada, 1: tornada) per dibuixar amb decalatge.
        """
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.track_id = track_id
        
        # Càlcul de geometria estàtica
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        self.pixel_length = math.sqrt(dx*dx + dy*dy)
        
        # Distància "real" per a la simulació física
        self.real_length_km = self.pixel_length * Edge.PIXELS_TO_KM
        
        # Inicialitzem propietats de velocitat
        self.update_properties()

    def update_properties(self):
        """
        Recalcula les velocitats màximes i els temps esperats segons el tipus de via.
        Es crida quan una via es trenca (OBSTACLE) o es repara (NORMAL).
        """
        # 1. VELOCITAT FÍSICA (Límit real del tren)
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0 
        else: 
            self.max_speed_kmh = 10.0 # Avaria greu
        
        # 2. VELOCITAT COMERCIAL (Per calcular horaris teòrics)
        # Augmentem el marge perquè el calendari sigui més realista amb l'accel./frenada.
        reference_speed = 90.0 if self.edge_type == EdgeType.NORMAL else 10.0

        if reference_speed > 0:
            hours_min = self.real_length_km / reference_speed
            # Padding més ampli (60%) per absorbir arrencades, frenades i parada obligada.
            hours_scheduled = hours_min * 1.60
            self.expected_minutes = hours_scheduled * 60
        else:
            self.expected_minutes = 999.0

    def draw(self, screen):
        """Dibuixa la línia entre estacions. Vermell si està trencada, Gris si està bé."""
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        
        # Càlcul bàsic de línia
        start = (self.node1.x, self.node1.y)
        end = (self.node2.x, self.node2.y)
        
        pygame.draw.line(screen, color, start, end, width)