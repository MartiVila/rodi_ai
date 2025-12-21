import pygame
class Node:
    """
    Estructura de dades per a una estació
    """
    def __init__(self, x, y, node_id, name=""):
        # Coordenades al mapa
        self.x = x
        self.y = y
        
        self.id = node_id
        self.name = name
        self.radius = 5
        self.highlight = False
        # Guardem els veïns per saber on podem anar: {id_veí: [edge_via_1, edge_via_2]}
        self.neighbors = {}
        
        # --- APARTADEROS (SIDINGS) ---
        self.has_siding = False  # Si la estación tiene apartadero
        self.trains_in_siding = []  # IDs de trenes apartados aquí 

    def draw(self, screen):
        # Si tiene apartadero, dibujarlo con un rectángulo
        if self.has_siding:
            rect_size = 12
            pygame.draw.rect(screen, (100, 100, 100), 
                           (int(self.x) - rect_size//2, int(self.y) - rect_size//2, rect_size, rect_size), 2)
        
        color = (0, 100, 200) if not self.highlight else (255, 100, 0)
        # Si hay trenes apartados, color amarillo
        if len(self.trains_in_siding) > 0:
            color = (200, 200, 0)
        
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            text = font.render(self.name, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)