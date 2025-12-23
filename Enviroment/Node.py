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

    def draw(self, screen):
        # Color per defecte (Blau Marí)
        color = (0, 100, 200) 
        
        # Si és un apartador (SIDING), el pintem diferent (ex: Lila o Taronja fosc)
        # Fem servir getattr per seguretat si l'atribut no existís
        if getattr(self, 'is_siding', False):
            color = (128, 0, 128) # Lila per indicar capacitat d'apartar
        # Si està destacat (Highlight), prioritat màxima (Taronja)
        if self.highlight:
            color = (255, 100, 0)

        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            text = font.render(self.name, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)