import pygame

class Node:
    """
    Representa una estació o punt d'interès en el graf ferroviari.
    
    Atributs:
    - id (str): Identificador únic (normalment del CSV).
    - x, y (float): Coordenades de pantalla (píxels).
    - name (str): Nom llegible de l'estació (ex: "BARCELONA-SANTS").
    - neighbors (dict): Diccionari d'adjacència {neighbor_id: [Edge, Edge]}.
    """

    def __init__(self, x, y, node_id, name=""):
        self.x = x
        self.y = y
        self.id = node_id
        self.name = name
        
        # Visuals
        self.radius = 5
        self.highlight = False
        
        # Graf: Llista d'arestes connectades per ID de destí
        self.neighbors = {} 

    def draw(self, screen):
        """
        Renderitza el node al mapa.
        Canvia de color si és un apartador o si està destacat pel ratolí.
        """
        # Color base: Blau Marí
        color = (0, 100, 200) 
        
        # Si és un apartador (atribut dinàmic injectat per Datas), color Lila
        if getattr(self, 'is_siding', False):
            color = (128, 0, 128) 

        # Highlight (Ratolí a sobre o debug): Taronja brillant
        if self.highlight:
            color = (255, 100, 0)

        # 1. Dibuix del punt
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        
        # 2. Etiqueta de nom (només si està destacat)
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            text = font.render(self.name, True, (50, 50, 50))
            
            # Centrem l'etiqueta sobre el punt
            bg = text.get_rect(center=(self.x, self.y - 15))
            
            # Fons blanc per llegibilitat
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)