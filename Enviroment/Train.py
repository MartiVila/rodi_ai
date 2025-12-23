import pygame
import os
from.Datas import Datas
# [MODIFICACIÓ] Ajusta els imports segons la teva estructura real
from .EdgeType import EdgeType
from Agent import QlearningAgent 
from .TrafficManager import TrafficManager

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
        if os.path.exists("q_table.pkl"):
            self.agent.load_table("q_table.pkl")
        elif os.path.exists("Agent/Qtables/q_table.pkl"):
            self.agent.load_table("Agent/Qtables/q_table.pkl")

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
        if self.finished: return

        # 1. Obtenir tram
        segment = self.current_segment()
        if not segment:
            self.finished = True
            return
        
        origin_name, target_name = segment

        # 2. Inicialització Visual i Càlcul de Temps
        # Si canviem de tram o acabem de començar (node és None)
        if self.node is None or self.target is None:
            if hasattr(self, 'nodes_map') and self.nodes_map:
                self.node = self.nodes_map.get(origin_name)
                self.target = self.nodes_map.get(target_name)
                
                # [NOU] Recuperem l'objecte Edge real per saber track_id i propietats
                self.current_edge = TrafficManager.get_edge(origin_name, target_name)

                # Càlcul de temps (amb penalització per obstacles)
                base_time = Datas.R1_TIME.get(segment, 3.0)
                penalty_factor = TrafficManager.get_segment_status(origin_name, target_name)
                self.current_travel_duration = base_time * penalty_factor
                
                if penalty_factor > 1.0:
                     print(f"⚠️ Tren {self.train_id} alentit per OBSTACLE a {origin_name}->{target_name}")
            else:
                return

        # 3. Avançar progrés
        if self.current_travel_duration > 0:
            self.progress += dt / self.current_travel_duration
        else:
            self.progress = 1.0

        # 4. Comprovar arribada
        if self.progress >= 1.0:
            self.idx += 1
            self.progress = 0.0
            self.scheduled_time += self.current_travel_duration
            self.real_time += self.current_travel_duration 
            
            # Resetegem nodes per forçar la búsqueda del següent tram al proper update
            self.node = None
            self.target = None
            self.current_edge = None 


    def current_segment(self):
        """Retorna el segmento actual (origen, destino) o None si terminó"""
        if self.idx >= len(self.route) - 1:
            return None
        return (self.route[self.idx], self.route[self.idx + 1])

    

    def draw(self, screen):
        if self.finished: return
        if not self.node or not self.target: return

        # Color segons estat
        color = (0, 200, 0) 
        if abs(self.delay_global) > 5: color = (230, 140, 0) 
        if self.collision_detected: color = (0, 0, 0) 
        
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        
        # [MODIFICACIÓ CLAU] Offset idèntic a Edge.py (3 i -3)
        off = 0
        if self.current_edge:
            # Edge.py fa servir 3 per track 0 i -3 per track 1. Fem el mateix.
            off = 4 if self.current_edge.track_id == 0 else 3
            
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        
        # Vector perpendicular unitari
        perp_x = -dy / dist
        perp_y = dx / dist
        
        safe_progress = min(1.0, max(0.0, self.progress))
        
        # Coordenades finals amb l'offset corregit
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)

    ############################################################################################
    ########################   MÈTODES DE PERSISTÈNCIA   #######################################
    ############################################################################################

    def save_table(self, filename="Agent/Qtables/q_table.pkl"):
        """Delega el guardat al seu propi agent"""
        self.agent.save_table(filename)

    def load_table(self, filename="Agent/Qtables/q_table.pkl"):
        """Delega la càrrega al seu propi agent"""
        self.agent.load_table(filename)