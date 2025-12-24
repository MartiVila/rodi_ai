import pygame
from Enviroment.TrafficManager import TrafficManager

class RodaliesAI:
    # Configuració de la simulació
    TIME_SCALE = 10.0      
    
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies AI - Simulation View")
        self.clock = pygame.time.Clock()
        self.running = True

        # === INSTANCIACIÓ DEL GESTOR DE TRÀNSIT ===
        # Tot passa aquí dins. Li passem mides per la generació del mapa.
        self.manager = TrafficManager(self.width, self.height)
        
        print("Sistema iniciat. Control delegat a TrafficManager.")

    def run(self):
        try:
            while self.running:
                # 1. Càlcul del temps delta
                dt_ms = self.clock.tick(60)       
                dt_real_seconds = dt_ms / 1000.0          
                dt_sim_minutes = dt_real_seconds * self.TIME_SCALE 

                # 2. Events de l'Usuari (Input)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: 
                        self.running = False

                    if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_d:
                                print("\n--- DEBUG MANUAL ACTIVAT ---")
                                self.manager.debug_network_snapshot()
                                self.manager.brain.debug_qtable_stats()


                # 3. DELEGACIÓ: El Manager actualitza tot l'estat
                self.manager.update(dt_sim_minutes)

                # 4. VISUALITZACIÓ
                self.screen.fill((240, 240, 240))
                
                # Accedim a les dades del manager NOMÉS per dibuixar
                # (L'UI llegeix l'estat, no el modifica)
                for e in self.manager.all_edges: 
                    e.draw(self.screen)
                    
                for n in self.manager.nodes.values(): 
                    n.draw(self.screen)
                    
                for t in self.manager.active_trains: 
                    t.draw(self.screen)
                
                # HUD / Informació en pantalla
                self._draw_hud()

                pygame.display.flip()
            
        except Exception as e:
            print(f"Error inesperat: {e}")
            import traceback
            traceback.print_exc() # Més info per debug
        finally:
            # En tancar, demanem al manager que guardi el que calgui
            if hasattr(self, 'manager'):
                self.manager.save_brain()
            pygame.quit()
            print("Simulació finalitzada.")

    def _draw_hud(self):
        debug_font = pygame.font.SysFont("Arial", 16)
        
        # Obtenim dades del manager
        sim_time = self.manager.sim_time
        num_trains = len(self.manager.active_trains)
        
        days = int(sim_time // 1440)
        hours = int((sim_time % 1440) // 60)
        mins = int(sim_time % 60)
        
        time_str = f"Dia {days} | {hours:02d}:{mins:02d}"
        info_str = f"{time_str} | Trens actius: {num_trains} | Scale: x{self.TIME_SCALE}"
        
        msg = debug_font.render(info_str, True, (0,0,0))
        self.screen.blit(msg, (10, 10))

if __name__ == "__main__":
    RodaliesAI().run()