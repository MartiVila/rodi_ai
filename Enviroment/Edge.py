import math
import pygame
from .EdgeType import EdgeType

class Edge:
    PIXELS_TO_KM = 0.05 

    def __init__(self, node1, node2, edge_type, track_id, reverse_draw=False):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        self.track_id = track_id
        self.reverse_draw = reverse_draw
        
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        self.pixel_length = math.sqrt(dx*dx + dy*dy)
        self.real_length_km = self.pixel_length * Edge.PIXELS_TO_KM
        
        self.update_properties()

    def update_properties(self):
        if self.edge_type == EdgeType.NORMAL:
            self.max_speed_kmh = 160.0
        elif self.edge_type == EdgeType.URBAN:
            self.max_speed_kmh = 85.0
        else: # OBSTACLE
            self.max_speed_kmh = 0.0 # This ensures trains stop!

        if self.max_speed_kmh > 0:
            hours_min = self.real_length_km / self.max_speed_kmh
            hours_scheduled = hours_min * 1.25
            self.expected_minutes = hours_scheduled * 60
        else:
            self.expected_minutes = 999 

        if self.expected_minutes > 0:
            self.vis_speed = 1.0 / self.expected_minutes
        else:
            self.vis_speed = 1.0

    def draw(self, screen):
        color = (180, 180, 180) if self.edge_type == EdgeType.NORMAL else (200, 0, 0)
        width = 2
        
        base_off = 3 if self.track_id == 0 else -3
        if self.reverse_draw:
            base_off = -base_off
            
        dx = self.node2.x - self.node1.x
        dy = self.node2.y - self.node1.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0: dist = 1
        perp_x = -dy / dist
        perp_y = dx / dist
        
        start = (self.node1.x + perp_x * base_off, self.node1.y + perp_y * base_off)
        end = (self.node2.x + perp_x * base_off, self.node2.y + perp_y * base_off)
        
        pygame.draw.line(screen, color, start, end, width)