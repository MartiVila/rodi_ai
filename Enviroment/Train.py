import pygame
import math
from.Datas import Datas
# [MODIFICACIÓ] Ajusta els imports segons la teva estructura real
from .EdgeType import EdgeType
from Agent import QlearningAgent 

class TrainStatus:
    SENSE_RETARD = "ON TIME"     
    RETARD_MODERAT = "DELAYED" # O "EARLY" en aquest cas
    AVARIAT = "BROKEN"           

class Train:
    # FÍSICA
    ACCELERATION = 30.0   
    BRAKING = 80.0        
    SAFE_DISTANCE_PCT = 0.05 

    """
    ############################################################################################
    ############################################################################################

    Classe base per crear Objectes trens gestionants per Qlearning Agent

    Els trens tenen un delay local i global

    ############################################################################################
    ############################################################################################
    
    """

    def __init__(self, train_id, start_delay=0, route_idx=None):
        """
        Docstring for __init__
        
        :param train_id: Id del tren a crear
        :param start_delay: Minuts inicials de retard
        :param route_idx: Per quina Via i quina ruta anirà
        """

        self.train_id = train_id
        
        # [MODIFICACIÓ] Cada tren instancia el seu propi agent
        self.agent = QlearningAgent.QLearningAgent()
        
        # Seleccionar ruta: si no se especifica, usar basada en ID
        if route_idx is None:
            route_idx = train_id % len(Datas.R1_ROUTES)
        self.route_idx = route_idx
        self.route = Datas.R1_ROUTES[route_idx]
        
        self.idx = 0  # índice en su ruta
        self.real_time = start_delay
        self.scheduled_time = start_delay
        self.done = False
        self.waiting_at_station = False  # True si está esperando en estación
        self.wait_time = 0  # tiempo acumulado esperando

        # [NOU] --- VARIABLES VISUALS ---
        # Afegides per permetre que la funció draw() funcioni sense errors
        self.node = None          # Node origen gràfic
        self.target = None        # Node destí gràfic
        self.current_edge = None  # Via actual
        self.progress = 0.0       # 0.0 a 1.0 entre estacions
        self.finished = False     # Sinònim de done per al visual
        self.delay_global = 0     # Per canviar el color
        self.collision_detected = False
        self.last_departure_time = start_delay # Per interpolació visual

    def reset(self, start_delay=0):
        self.idx = 0
        self.real_time = start_delay
        self.scheduled_time = start_delay
        self.done = False
        self.waiting_at_station = False
        self.wait_time = 0
        
        # [NOU] Reset visual
        self.finished = False
        self.progress = 0.0
        self.last_departure_time = start_delay

    def update(self, dt):
        """
        Actualitza l'estat del tren en funció del temps transcorregut (dt).
        Gestiona el moviment visual (interpolació) i el canvi lògic d'estació.
        """
        if self.finished: return

        # 1. Obtenir el tram actual (Origen -> Destí)
        segment = self.current_segment()
        if not segment:
            self.finished = True
            return
        
        origin_name, target_name = segment

        # 2. Inicialització Visual (Només quan entrem en un nou tram)
        # Necessitem 'nodes_map' que hem injectat en el pas anterior
        if self.node is None or self.target is None:
            if hasattr(self, 'nodes_map') and self.nodes_map:
                self.node = self.nodes_map.get(origin_name)
                self.target = self.nodes_map.get(target_name)
                
                # Determinar durada del trajecte per calcular la velocitat visual
                # Si no troba el temps al diccionari, assumeix 3 minuts per defecte
                self.current_travel_duration = Datas.R1_TIME.get(segment, 3.0)
            else:
                # Si no tenim mapa, no podem calcular posició visual
                return

        # 3. Avançar el progrés (Interpolació Lineal)
        # dt són els minuts simulats que han passat des de l'últim frame
        if self.current_travel_duration > 0:
            self.progress += dt / self.current_travel_duration
        else:
            self.progress = 1.0 # Salt instantani si durada és 0

        # 4. Comprovar arribada a l'estació destí
        if self.progress >= 1.0:
            # Hem arribat: passem al següent índex de la ruta
            self.idx += 1
            self.progress = 0.0
            
            # Actualitzem temps lògics (simplificat per visualització)
            self.scheduled_time += self.current_travel_duration
            self.real_time += self.current_travel_duration 
            
            # El destí actual passa a ser el nou origen
            self.node = self.target
            self.target = None # Forcem a buscar el següent target al pròxim update


    def current_segment(self):
        """Retorna el segmento actual (origen, destino) o None si terminó"""
        if self.idx >= len(self.route) - 1:
            return None
        return (self.route[self.idx], self.route[self.idx + 1])

    def draw(self, screen):
        # [MODIFICACIÓ] Petita protecció inicial per si el context visual no està llest
        if self.finished: return
        if not self.node or not self.target: return

        color = (0, 200, 0) 
        if abs(self.delay_global) > 5: color = (230, 140, 0) 
        if self.collision_detected: color = (0, 0, 0) 
        
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        # [MODIFICACIÓ] Protecció per si current_edge encara és None
        off = 0
        if self.current_edge:
            off = 5 if self.current_edge.track_id == 0 else -5
            
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # [MODIFICACIÓ] Assegurar que progress està entre 0 i 1
        safe_progress = min(1.0, max(0.0, self.progress))
        
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)