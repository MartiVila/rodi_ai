import pygame
import sys
import traceback
from Enviroment.TrafficManager import TrafficManager

class RodaliesAI:
    """
    Classe principal de l'aplicació (Main Entry Point).
    
    Responsabilitats:
    1. Inicialitzar el motor gràfic (Pygame).
    2. Instanciar el gestor de la simulació (TrafficManager).
    3. Gestionar el bucle principal (Input -> Update -> Render).
    4. Gestionar el temps de simulació vs temps real.
    """

    # Configuració global de la simulació
    TIME_SCALE = 5.0  # Factor de temps: 1 segon real = 10 minuts simulats
    FPS = 60           # Frames per segon objectiu

    """
    ############################################################################################
    ############################################################################################

    Inicialització del Sistema i Gestor de Trànsit

    ############################################################################################
    ############################################################################################
    """

    def __init__(self):
        """
        Inicialitza la finestra, el rellotge i delega la construcció del món
        al TrafficManager.
        """
        pygame.init()
        
        # Configuració de la finestra
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies AI - Simulation View")
        
        self.clock = pygame.time.Clock()
        self.running = True

        # === INSTANCIACIÓ DEL GESTOR DE TRÀNSIT (MODEL) ===
        # El TrafficManager s'encarrega de carregar CSVs, crear nodes, 
        # vies i gestionar la lògica dels trens.
        self.manager = TrafficManager(self.width, self.height)
        
        print("Sistema iniciat. Control delegat a TrafficManager.")

    """
    ############################################################################################
    ############################################################################################

    Bucle Principal (Main Loop)
     - Gestió de Temps
     - Input d'Usuari
     - Actualització i Dibuix

    ############################################################################################
    ############################################################################################
    """

    def run(self):
        """
        Executa el bucle principal de la simulació.
        Gestiona les excepcions per assegurar que el 'cervell' (Q-Table) es guardi
        fins i tot si el programa falla.
        """
        try:
            while self.running:
                # 1. CÀLCUL DEL TEMPS (DELTA TIME)
                dt_ms = self.clock.tick(self.FPS)       
                dt_real_seconds = dt_ms / 1000.0          
                dt_sim_minutes = dt_real_seconds * self.TIME_SCALE 

                # 2. GESTIÓ D'INPUTS (CONTROLLER)
                self._handle_input()

                # 3. ACTUALITZACIÓ DE LÒGICA (MODEL)
                # Deleguem al manager l'avanç de l'estat del món
                self.manager.update(dt_sim_minutes)

                # 4. VISUALITZACIÓ (VIEW)
                self._draw()

        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            traceback.print_exc() # Imprimeix l'stack trace complet per debug
        
        finally:
            self._cleanup()

    def _handle_input(self):
        """Processa els esdeveniments de teclat i ratolí de Pygame."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT: 
                self.running = False

            if event.type == pygame.KEYDOWN:
                # Tecla D: Debug manual instantani
                if event.key == pygame.K_d:
                    print("\n--- DEBUG MANUAL ACTIVAT ---")
                    self.manager.debug_network_snapshot()
                    if hasattr(self.manager, 'brain'):
                        self.manager.brain.debug_qtable_stats()

    def _draw(self):
        # Importem l'Enum aquí per poder comprovar el tipus d'aresta (OBSTACLE vs NORMAL)
        from Enviroment.EdgeType import EdgeType

        self.screen.fill((240, 240, 240)) 
        
        # -------------------------------------------------------------
        # 1. AGRUPACIÓ DE VIES FÍSIQUES
        # Agrupem les direccions (A->B i B->A) per saber si alguna està trencada.
        # -------------------------------------------------------------
        segment_groups = {}

        for e in self.manager.all_edges:
            # Creem un ID únic per al tram físic, independent de la direcció
            n1_name = e.node1.name
            n2_name = e.node2.name
            
            # Ordenem els noms perquè (Sant Pol, Calella) i (Calella, Sant Pol) siguin el mateix
            sorted_pair = tuple(sorted((n1_name, n2_name)))
            
            # La clau identifica el tros de metall específic (Tram + ID de via)
            segment_id = (sorted_pair, e.track_id)

            if segment_id not in segment_groups:
                segment_groups[segment_id] = []
            segment_groups[segment_id].append(e)

        # -------------------------------------------------------------
        # 2. DIBUIX INTEL·LIGENT (PRIORITZANT OBSTACLES)
        # -------------------------------------------------------------
        for segment_id, edges in segment_groups.items():
            # Per defecte, agafem la primera via que trobem (probablement NORMAL/Gris)
            edge_to_draw = edges[0]
            
            # Recorrem TOTES les direccions d'aquest tram (anada i tornada)
            # Si ALGUNA està marcada com OBSTACLE, la seleccionem per dibuixar-la.
            for e in edges:
                if e.edge_type == EdgeType.OBSTACLE:
                    edge_to_draw = e  # Aquesta té color vermell definit al seu mètode .draw()
                    break
            
            # Dibuixem l'aresta escollida (si n'hi ha una de vermella, serà la vermella)
            edge_to_draw.draw(self.screen)
            
        # -------------------------------------------------------------
        # 3. DIBUIX DE NODES, TRENS I HUD
        # -------------------------------------------------------------
        for n in self.manager.nodes.values(): 
            n.draw(self.screen)
            
        for t in self.manager.active_trains: 
            t.draw(self.screen)
        
        self._draw_hud()
        pygame.display.flip()

    def _cleanup(self):
        """Tasques de neteja i guardat de dades abans de tancar."""
        print("Tancant simulació...")
        # Assegurem que el manager guardi l'aprenentatge (Q-Table)
        if hasattr(self, 'manager'):
            print("Guardant estat del cervell (Q-Learning)...")
            self.manager.save_brain()
        
        pygame.quit()
        sys.exit()

    """
    ############################################################################################
    ############################################################################################

    Funcions Auxiliars de la Interfície (HUD)

    ############################################################################################
    ############################################################################################
    """

    def _draw_hud(self):
        """Dibuixa la informació de text (Heads-Up Display) sobre la simulació."""
        debug_font = pygame.font.SysFont("Arial", 16)
        
        # Dades del model
        sim_time = self.manager.sim_time
        num_trains = len(self.manager.active_trains)
        
        # Conversió de minuts totals a Dies/Hores/Minuts
        days = int(sim_time // 1440)
        hours = int((sim_time % 1440) // 60)
        mins = int(sim_time % 60)
        
        time_str = f"Dia {days} | {hours:02d}:{mins:02d}"
        info_str = f"{time_str} | Trens actius: {num_trains} | Scale: x{self.TIME_SCALE}"
        
        msg = debug_font.render(info_str, True, (0, 0, 0))
        
        # Marge de 10px
        self.screen.blit(msg, (10, 10))

if __name__ == "__main__":
    RodaliesAI().run()