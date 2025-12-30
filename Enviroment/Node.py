import pygame

class Node:
    """
    representa una estacio
    acqui el tren pot fer canvi de via, i parase
    """

    def __init__(self, x, y, node_id, name=""):
        self.x = x
        self.y = y
        self.id = node_id
        self.name = name
        
        #varibales visuals
        self.radius = 5
        self.highlight = False
        
        #les vies connectades a l'esatció
        self.neighbors = {} 

        #trns que hi poden parar a la vegada i els que hi han ara
        self.max_capacity = 4
        self.current_trains = 0 

    def has_capacity(self):
        #per saber si hi ha espai per parar el tren
        return self.current_trains < self.max_capacity

    def enter_station(self):
        self.current_trains += 1

    def exit_station(self):
        if self.current_trains > 0:
            self.current_trains -= 1

    def draw(self, screen):
        color = (0, 100, 200) 
        
        if getattr(self, 'is_siding', False):
            color = (128, 0, 128) 

        #Si l'estació està plena, canvia el color a vermell fosc
        if self.current_trains >= self.max_capacity:
            color = (150, 0, 0)

        if self.highlight:
            color = (255, 100, 0)

        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        
        if self.highlight:
            font = pygame.font.SysFont("Arial", 14, bold=True)
            info_text = f"{self.name} [{self.current_trains}/{self.max_capacity}]"
            text = font.render(info_text, True, (50, 50, 50))
            bg = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg)
            screen.blit(text, bg)