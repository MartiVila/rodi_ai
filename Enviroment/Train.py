import pygame
import math
from Enviroment.Datas import Datas

class Train:
    """
    Classe que representa un tren individual.
    """

    # --- Constants Físiques ---
    ACCELERATION = 40.0     # km/h per minut simulat
    BRAKING = 80.0          # km/h per minut simulat
    MAX_SPEED_TRAIN = 120.0 
    
    # NOVETAT: Distància per començar a frenar (300m = 0.3km)
    BRAKING_DISTANCE_KM = 0.3 

    def __init__(self, agent, route_nodes, schedule, start_time_sim, is_training=False):
        self.agent = agent
        self.route_nodes = route_nodes
        self.schedule = schedule
        self.is_training = is_training

        self.id = id(self)
        self.finished = False
        
        self.current_node_idx = 0
        self.node = self.route_nodes[0]
        self.target = self.route_nodes[1] if len(route_nodes) > 1 else None
        
        self.current_speed = 0.0
        self.distance_covered = 0.0
        self.total_distance = 1.0
        self.max_speed_edge = 100.0
        
        self.sim_time = start_time_sim
        
        # --- NOVETAT: ESTATS D'ESPERA ---
        self.is_waiting = False    # Si està parat a l'estació
        self.wait_timer = 0.0      # Comptador de temps d'espera
        self.WAIT_TIME_MIN = 1.5   # Temps d'espera per estació (minuts simulats)

        self.setup_segment()

    def setup_segment(self):
        """Configura el nou tram."""
        if not self.target:
            self.finished = True
            return

        from Enviroment.TrafficManager import TrafficManager
        edge = TrafficManager.get_edge(self.node.name, self.target.name)
        
        if edge:
            self.current_edge = edge
            self.total_distance = edge.real_length_km
            self.max_speed_edge = edge.max_speed_kmh
        else:
            self.current_edge = None
            self.total_distance = 2.0 
            self.max_speed_edge = 80.0
            
        self.distance_covered = 0.0
        
        # [CORRECCIÓ] Eliminem l'impuls inicial de 10km/h perquè surti parat.
        # self.current_speed es manté com venia (0 si sortim d'estació).

    def calculate_delay(self):
        if not self.target: return 0
        expected_arrival = self.schedule.get(self.target.id)
        if expected_arrival is None: return 0
        return self.sim_time - expected_arrival

    # ---------------- FÍSICA ----------------

    def accelerate(self, dt_minutes):
        self.current_speed += self.ACCELERATION * dt_minutes
        limit = min(self.MAX_SPEED_TRAIN, self.max_speed_edge)
        if self.current_speed > limit:
            self.current_speed = limit

    def brake(self, dt_minutes):
        self.current_speed -= self.BRAKING * dt_minutes
        if self.current_speed < 0:
            self.current_speed = 0

    def move(self, dt_minutes):
        distance_step = self.current_speed * (dt_minutes / 60.0)
        self.distance_covered += distance_step

    # ---------------- BUCLE PRINCIPAL ----------------

    def update(self, dt_minutes):
        if self.finished: return
        self.sim_time += dt_minutes
        
        # [NOVETAT] Gestió de l'espera a l'estació (Boarding)
        if self.is_waiting:
            self.wait_timer -= dt_minutes
            if self.wait_timer <= 0:
                self.depart_from_station()
            return # Si estem esperant, no ens movem ni decidim res

        from Enviroment.TrafficManager import TrafficManager
        
        # 1. Estat i IA
        delay = self.calculate_delay()
        discrete_diff = self.agent.discretize_diff(int(delay))
        tid = self.current_edge.track_id if self.current_edge else 0
        is_blocked = TrafficManager.check_alert(self.node.name, self.target.name, tid)
        state = (self.node.name, self.target.name, discrete_diff, is_blocked)
        
        action_idx = self.agent.action(state)

        # 2. [NOVETAT IMPORTANT] Sobreescriptura per FRENADA A 300m
        # Calculem distància restant
        dist_remaining = self.total_distance - self.distance_covered
        
        if dist_remaining <= self.BRAKING_DISTANCE_KM:
            # Lògica d'aproximació:
            # Si estem a prop, la velocitat màxima ha de baixar proporcionalment a la distància.
            # Exemple: a 0.3km -> max 60km/h. A 0.1km -> max 20km/h.
            target_approach_speed = (dist_remaining / self.BRAKING_DISTANCE_KM) * 60.0 + 5.0
            
            if self.current_speed > target_approach_speed:
                # Si anem més ràpid del que toca per l'aproximació, FORCEM FRENAR
                action_idx = 2 # FRENAR
            elif action_idx == 0: 
                # Si l'agent vol accelerar però estem molt a prop, ho canviem a MANTENIR
                action_idx = 1 

        # 3. Executar Acció Física
        if action_idx == 0:
            self.accelerate(dt_minutes)
        elif action_idx == 1:
            pass 
        elif action_idx == 2:
            self.brake(dt_minutes)
            
        # 4. Actualitzar Posició
        self.move(dt_minutes)
        
        progress_pct = self.distance_covered / self.total_distance if self.total_distance > 0 else 0
        TrafficManager.update_train_position(self.current_edge, self.id, progress_pct)

        # 5. Arribada
        if self.distance_covered >= self.total_distance:
            self.arrive_at_station_logic(state, action_idx, delay)

    def arrive_at_station_logic(self, old_state, last_action, delay):
        """Gestiona l'arribada, recompenses i posa el tren en mode ESPERA"""
        
        # ... (Càlcul de recompenses igual que abans per a l'entrenament) ...
        # Pots mantenir el codi de rewards original aquí si estàs entrenant
        
        # En lloc de canviar de tram immediatament, activem l'espera
        self.current_speed = 0.0 # Assegurem que para completament
        self.distance_covered = self.total_distance # Visualment al final
        
        # Iniciem espera
        self.is_waiting = True
        self.wait_timer = self.WAIT_TIME_MIN
        
        # Debug
        # print(f"Tren {self.id} arribat a {self.target.name}. Esperant {self.WAIT_TIME_MIN} min.")

    def depart_from_station(self):
        """Surt de l'estació cap al següent tram després de l'espera"""
        from Enviroment.TrafficManager import TrafficManager
        
        self.is_waiting = False
        self.current_node_idx += 1
        self.node = self.target
        
        if self.current_node_idx < len(self.route_nodes) - 1:
            self.target = self.route_nodes[self.current_node_idx + 1]
            self.setup_segment() # Això posarà distance_covered a 0
        else:
            self.finished = True
            self.target = None
            TrafficManager.remove_train(self.id)

    # ---------------- VISUALITZACIÓ ----------------

    def draw(self, screen):
        if self.finished or not self.node or not self.target: return

        # Color segons estat
        if self.is_waiting:
            color = (255, 255, 0) # Groc quan està parat a l'estació
        else:
            delay = self.calculate_delay()
            if abs(delay) <= 2: color = (0, 255, 0)
            elif delay > 2:     color = (255, 0, 0)
            else:               color = (0, 0, 255)

        start_x, start_y = self.node.x, self.node.y
        # Si estem esperant, ens dibuixem exactament al node target (que ara és node actual logicament)
        # Però com que encara no hem fet el swap de variables fins al depart,
        # usem la interpolació al 100%
        
        end_x, end_y = self.target.x, self.target.y
        
        off = 0
        if self.current_edge:
            off = 4 if self.current_edge.track_id == 0 else -4
            
        dx = end_x - start_x
        dy = end_y - start_y
        dist_px = math.sqrt(dx**2 + dy**2)
        if dist_px == 0: dist_px = 1
        
        perp_x = -dy / dist_px
        perp_y = dx / dist_px
        
        progress = self.distance_covered / self.total_distance
        progress = max(0.0, min(1.0, progress))
        
        cur_x = start_x + dx * progress + perp_x * off
        cur_y = start_y + dy * progress + perp_y * off
        
        pygame.draw.circle(screen, color, (int(cur_x), int(cur_y)), 6)

        
    #-------------------DEBUG------------------

    def __repr__(self):
        """Representació text del tren per a prints ràpids"""
        origen = self.node.name if self.node else "?"
        desti = self.target.name if self.target else "?"
        return f"[T-{self.id % 1000}] {origen} -> {desti} (v={self.current_speed:.1f})"

    def debug_status(self):
        """Imprimeix estat físic i d'horari detallat"""
        delay = self.calculate_delay()
        estat_str = "A TEMPS"
        if delay > 2: estat_str = f"RETARD (+{delay:.1f}m)"
        elif delay < -2: estat_str = f"AVANÇAT ({delay:.1f}m)"
        
        print(f"=== DEBUG TREN {self.id} ===")
        print(f"📍 Posició: {self.distance_covered:.2f}/{self.total_distance:.2f} km")
        print(f"🚄 Velocitat: {self.current_speed:.1f} km/h (Max Via: {self.max_speed_edge})")
        print(f"⏱️  Estat: {estat_str} | SimTime: {self.sim_time:.1f}")
        print("---------------------------")

    def debug_agent_decision(self, state, action, reward=None):
        """
        Crida això DINS del mètode update() just després de self.agent.action()
        per veure què està pensant.
        """
        acciones = {0: "ACCELERAR", 1: "MANTENIR", 2: "FRENAR"}
        nom_accio = acciones.get(action, "UNKNOWN")
        
        # Recuperem els Q-values per a aquest estat per veure les opcions
        q_values = [self.agent.q[(state, a)] for a in range(3)]
        
        print(f"🧠 [CERVELL TREN {self.id}]")
        print(f"   Estat Percebut: {state}")
        print(f"   Valors Q: {q_values}") # Ex: [0.5, 0.2, -1.0]
        print(f"   👉 Acció Escollida: {nom_accio} ({action})")
        if reward is not None:
             print(f"   🎁 Recompensa rebuda: {reward}")