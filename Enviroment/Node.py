import pygame
class Node:
    def __init__(self, x, y, node_id, name=""):
        self.x = x
        self.y = y
        self.id = node_id
        self.name = name
        self.radius = 5
        self.highlight = False
        # Guardem els veïns per saber on podem anar: {id_veí: [edge_via_1, edge_via_2]}
        self.neighbors = {} 

    def draw(self, screen):
        color = (0, 100, 200) if not self.highlight else (255, 100, 0)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            text = font.render(self.name, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)