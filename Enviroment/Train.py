import pygame
import math
import Datas
from .EdgeType import EdgeType
from ..Agent import QlearningAgent

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
        self.agent = QlearningAgent()
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

    def reset(self, start_delay=0):
        self.idx = 0
        self.real_time = start_delay
        self.scheduled_time = start_delay
        self.done = False
        self.waiting_at_station = False
        self.wait_time = 0

    def current_segment(self):
        """Retorna el segmento actual (origen, destino) o None si terminó"""
        if self.idx >= len(self.route) - 1:
            return None
        return (self.route[self.idx], self.route[self.idx + 1])

    def draw(self, screen):
        # (El draw es manté igual, pots fer servir el que ja tenies)
        if self.finished: return
        color = (0, 200, 0) 
        if abs(self.delay_global) > 5: color = (230, 140, 0) 
        if self.collision_detected: color = (0, 0, 0) 
        
        start_x, start_y = self.node.x, self.node.y
        end_x, end_y = self.target.x, self.target.y
        off = 5 if self.current_edge.track_id == 0 else -5
        dx = end_x - start_x
        dy = end_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        safe_progress = min(1.0, self.progress)
        cur_x = start_x + dx * safe_progress + perp_x * off
        cur_y = start_y + dy * safe_progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)