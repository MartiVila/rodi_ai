import pygame

class Node:
    """
    Representa una estació o punt d'interès en el graf ferroviari.
    Ara inclou gestió de capacitat (Slots).
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

        # --- NOVETAT: CAPACITAT D'ESTACIÓ ---
        self.max_capacity = 4  # Màxim trens parats simultàniament
        self.current_trains = 0 # Comptador actual

    def has_capacity(self):
        """Retorna True si hi ha lloc per un altre tren."""
        return self.current_trains < self.max_capacity

    def enter_station(self):
        self.current_trains += 1

    def exit_station(self):
        if self.current_trains > 0:
            self.current_trains -= 1

    def draw(self, screen):
        # ... (Codi de dibuix sense canvis, excepte potser mostrar l'ocupació) ...
        # Color base: Blau Marí
        color = (0, 100, 200) 
        
        if getattr(self, 'is_siding', False):
            color = (128, 0, 128) 

        # Indicar visualment si l'estació està plena (Vermell fosc)
        if self.current_trains >= self.max_capacity:
            color = (150, 0, 0)

        if self.highlight:
            color = (255, 100, 0)

        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        
        # Opcional: Mostrar ocupació (ex: "Sants [3/4]")
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            info_text = f"{self.name} [{self.current_trains}/{self.max_capacity}]"
            text = font.render(info_text, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)