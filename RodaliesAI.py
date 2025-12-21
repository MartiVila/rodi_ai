import pygame
import random
import pandas as pd
import math
import re
import unicodedata
from geopy.distance import great_circle

from Enviroment.EdgeType import EdgeType
from Enviroment.Edge import Edge
from Enviroment.Node import Node
from Enviroment.Train import Train
import Agent.QlearningAgent as QLearningAgent
from Enviroment.TrafficManager import TrafficManager

class RodaliesAI:
    TIME_SCALE = 10.0      
    SPAWN_INTERVAL = 30    
    RESET_INTERVAL = 210  
    CHAOS_INTERVAL = 60   
    
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies AI - Full R1 Line")
        self.clock = pygame.time.Clock()
        self.running = True

        self.nodes = {}
        self.all_edges = []
        self.active_trains = []
        self.completed_trains_log = []
        self.siding_usage_count = 0 
        
        self.brain = QLearningAgent.QLearningAgent(epsilon=0.2)
        self.brain.load_table("q_table.pkl")

        self.sim_time = 0.0
        self.last_chaos = self.sim_time
        self.last_reset = self.sim_time
        self.last_spawn = self.sim_time

        self.load_real_data()

    def _normalize_name(self, name):
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = "".join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        if raw is None or (isinstance(raw, float) and math.isnan(raw)): return None
        s = str(raw).strip().replace('−', '-')
        digits = re.sub(r"[^0-9-]", "", s)
        try:
            val_int = int(digits)
            target, v_range = (41.5, (39.0, 44.0)) if is_lat else (2.0, (-1.0, 5.0))
            divisors = [10**i for i in range(10)]
            candidates = [val_int / d for d in divisors]
            hits = [c for c in candidates if v_range[0] <= c <= v_range[1]]
            return float(min(hits, key=lambda x: abs(x - target))) if hits else None
        except: return None

    def load_real_data(self):
        # --- FULL R1 CONNECTIONS ---
        self.r1_connections = [
            ('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'),
            ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
            ('SANTJOANDESPI', 'CORNELLA'),
            ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
            ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'),
            ('BARCELONASANTS', 'PLACADECATALUNYA'),
            ('PLACADECATALUNYA', 'ARCDETRIOMF'),
            ('ARCDETRIOMF', 'BARCELONACLOTARAGO'),
            ('BARCELONACLOTARAGO', 'SANTADRIADEBESOS'),
            ('SANTADRIADEBESOS', 'BADALONA'),
            ('BADALONA', 'MONTGAT'),
            ('MONTGAT', 'MONTGATNORD'),
            ('MONTGATNORD', 'ELMASNOU'),
            ('ELMASNOU', 'OCATA'),
            ('OCATA', 'PREMIADEMAR'),
            ('PREMIADEMAR', 'VILASSARDEMAR'),
            ('VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR'),
            ('CABRERADEMARVILASSARDEMAR', 'MATARO'),
            ('MATARO', 'SANTANDREUDELLAVANERES'),
            ('SANTANDREUDELLAVANERES', 'CALDESDESTRAC'),
            ('CALDESDESTRAC', 'ARENYSDEMAR'),
            ('ARENYSDEMAR', 'CANETDEMAR'),
            ('CANETDEMAR', 'SANTPOLDEMAR'),
            ('SANTPOLDEMAR', 'CALELLA'),
            ('CALELLA', 'PINEDADEMAR'),
            ('PINEDADEMAR', 'SANTASUSANNA'),
            ('SANTASUSANNA', 'MALGRATDEMAR'),
            ('MALGRATDEMAR', 'BLANES'),
            ('BLANES', 'TORDERA'),
            ('TORDERA', 'MACANETMASSANES')
        ]
        
        # Added main terminus stations to sidings list
        self.stations_with_sidings = [
            'SANTFELIUDELLOBREGAT', 'CORNELLA', 'BARCELONASANTS', 'PLACADECATALUNYA',
            'MATARO', 'BLANES', 'MACANETMASSANES' 
        ]

        wanted_stations = set()
        for s1, s2 in self.r1_connections:
            wanted_stations.add(self._normalize_name(s1))
            wanted_stations.add(self._normalize_name(s2))

        csv_path = 'Enviroment/data/estaciones_coordenadas.csv'
        try:
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            df.columns = [c.strip().upper() for c in df.columns]
        except Exception: return

        lats, lons, temp_st = [], [], []
        for _, row in df.iterrows():
            name = row.get('NOMBRE_ESTACION')
            norm_name = self._normalize_name(name)
            if norm_name not in wanted_stations: continue 

            lat, lon = self._parse_coord(row.get('LATITUD'), True), self._parse_coord(row.get('LONGITUD'), False)
            if name and lat and lon:
                temp_st.append({'id': str(row.get('ID')), 'norm': norm_name, 'orig': name, 'lat': lat, 'lon': lon})
                lats.append(lat)
                lons.append(lon)

        if not lats: return
        min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)

        for st in temp_st:
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * (self.width - 100) + 50
            y = self.height - (((st['lat'] - min_lat) / (max_lat - min_lat)) * (self.height - 100) + 50)
            
            node = Node(x, y, st['id'], name=st['orig'])
            node.lat, node.lon = st['lat'], st['lon']
            
            if st['norm'] in self.stations_with_sidings:
                node.has_siding = True
            
            self.nodes[st['norm']] = node

        self.build_R1()

    def add_connection(self, s1, s2):
        n1, n2 = self._normalize_name(s1), self._normalize_name(s2)
        if n1 in self.nodes and n2 in self.nodes:
            u, v = self.nodes[n1], self.nodes[n2]
            
            e_uv_0 = Edge(u, v, EdgeType.NORMAL, 0, reverse_draw=False)
            e_vu_0 = Edge(v, u, EdgeType.NORMAL, 0, reverse_draw=True)
            e_uv_0.partner_edge = e_vu_0
            e_vu_0.partner_edge = e_uv_0
            
            e_uv_1 = Edge(u, v, EdgeType.NORMAL, 1, reverse_draw=False)
            e_vu_1 = Edge(v, u, EdgeType.NORMAL, 1, reverse_draw=True)
            e_uv_1.partner_edge = e_vu_1
            e_vu_1.partner_edge = e_uv_1
            
            self.all_edges.extend([e_uv_0, e_uv_1, e_vu_0, e_vu_1])
            u.neighbors[v.id] = [e_uv_0, e_uv_1]
            v.neighbors[u.id] = [e_vu_0, e_vu_1]

    def build_R1(self):
        for s1, s2 in self.r1_connections: 
            self.add_connection(s1, s2)
        
        self.lines = {}
        # --- FULL ROUTE DEFINITION ---
        self.lines['R1_NORD'] = [
            'MOLINSDEREI', 'SANTFELIUDELLOBREGAT', 'SANTJOANDESPI', 'CORNELLA', 
            'LHOSPITALETDELLOBREGAT', 'BARCELONASANTS', 'PLACADECATALUNYA', 
            'ARCDETRIOMF', 'BARCELONACLOTARAGO', 'SANTADRIADEBESOS', 'BADALONA', 
            'MONTGAT', 'MONTGATNORD', 'ELMASNOU', 'OCATA', 'PREMIADEMAR', 
            'VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR', 'MATARO', 
            'SANTANDREUDELLAVANERES', 'CALDESDESTRAC', 'ARENYSDEMAR', 
            'CANETDEMAR', 'SANTPOLDEMAR', 'CALELLA', 'PINEDADEMAR', 
            'SANTASUSANNA', 'MALGRATDEMAR', 'BLANES', 'TORDERA', 'MACANETMASSANES'
        ]
        self.lines['R1_SUD'] = self.lines['R1_NORD'][::-1]

    def calculate_schedule(self, route_nodes, start_time):
        schedule = {}
        current_time = start_time
        if route_nodes:
            schedule[route_nodes[0].id] = current_time
        for i in range(len(route_nodes) - 1):
            u, v = route_nodes[i], route_nodes[i+1]
            if v.id in u.neighbors:
                edges = u.neighbors[v.id]
                travel_time = min(edge.expected_minutes for edge in edges)
                current_time += travel_time
                schedule[v.id] = current_time
            else: break
        return schedule

    def spawn_line_train(self, line_name):
        if line_name not in self.lines: return
        station_names = self.lines[line_name]
        route_nodes = [self.nodes[n] for n in station_names if n in self.nodes]
        
        if len(route_nodes) > 1:
            schedule = self.calculate_schedule(route_nodes, self.sim_time)
            new_train = Train(self.brain, route_nodes, schedule, self.sim_time)
            self.active_trains.append(new_train)

    def spawn_random_train(self):
        origins = [n for n in self.nodes.values() if n.neighbors]
        if not origins: return
        start = random.choice(origins)
        target_id = random.choice(list(start.neighbors.keys()))
        target = next(n for n in self.nodes.values() if n.id == target_id)
        
        route_nodes = [start, target]
        schedule = self.calculate_schedule(route_nodes, self.sim_time)
        self.active_trains.append(Train(self.brain, route_nodes, schedule, self.sim_time))

    def handle_mechanics(self):
        if self.sim_time - self.last_reset > self.RESET_INTERVAL:
            self.last_reset = self.sim_time
            for e in self.all_edges: 
                e.edge_type = EdgeType.NORMAL
                e.update_properties()
            
            TrafficManager.reset()
            print(f"Dia nou: Vies i Incidències netejades al minut {int(self.sim_time)}")

            for t in self.active_trains:
                if t.current_edge:
                    TrafficManager.update_train_position(t.current_edge, t.id, t.progress)
                    if t.collision_detected:
                         TrafficManager.report_issue(t.node.id, t.target.id, t.current_edge.track_id)
        
        if self.sim_time - self.last_chaos > self.CHAOS_INTERVAL:
            self.last_chaos = self.sim_time
            normals = [e for e in self.all_edges if e.edge_type == EdgeType.NORMAL]
            
            if len(normals) > 0:
                target_edge = random.choice(normals)
                target_edge.edge_type = EdgeType.OBSTACLE
                target_edge.update_properties()
                
                if hasattr(target_edge, 'partner_edge'):
                    target_edge.partner_edge.edge_type = EdgeType.OBSTACLE
                    target_edge.partner_edge.update_properties()
                    print(f"⚠️ [CHAOS] Track Broken: {target_edge.node1.name} <-> {target_edge.node2.name} (Track {target_edge.track_id})")

    def run(self):
        try:
            while self.running:
                dt_ms = self.clock.tick(60)       
                dt_real_seconds = dt_ms / 1000.0          
                dt_sim_minutes = dt_real_seconds * self.TIME_SCALE 
                self.sim_time += dt_sim_minutes

                for event in pygame.event.get():
                    if event.type == pygame.QUIT: self.running = False
                
                self.handle_mechanics()
                
                if self.sim_time - self.last_spawn > self.SPAWN_INTERVAL:
                    self.last_spawn = self.sim_time
                    rand = random.random()
                    
                    if rand < 0.40:
                        self.spawn_line_train('R1_NORD')
                    elif rand < 0.80:
                        self.spawn_line_train('R1_SUD')
                    else:
                        self.spawn_random_train()

                for t in self.active_trains: 
                    was_in_siding = getattr(t, '_was_in_siding', False)
                    if t.is_in_siding and not was_in_siding:
                        self.siding_usage_count += 1
                        t._was_in_siding = True
                    elif not t.is_in_siding:
                        t._was_in_siding = False
                    
                    t.update(dt_sim_minutes)
                
                finished_trains = [t for t in self.active_trains if t.finished]
                for t in finished_trains:
                    self.completed_trains_log.append({
                        "id": str(t.id)[-4:],
                        "origin": t.route[0].id if t.route else "?",
                        "dest": t.route[-1].id if t.route else "?",
                        "delay": t.delay_global,
                        "status": t.status
                    })
                    print(f"📝 [REPORT] Train {str(t.id)[-4:]} finished. Delay: {t.delay_global:.2f} min.")
                
                self.active_trains = [t for t in self.active_trains if not t.finished]

                self.screen.fill((240, 240, 240))
                for e in self.all_edges: e.draw(self.screen)
                for n in self.nodes.values(): n.draw(self.screen)
                for t in self.active_trains: t.draw(self.screen)
                
                debug_font = pygame.font.SysFont("Arial", 16)
                days = int(self.sim_time // 1440)
                hours = int((self.sim_time % 1440) // 60)
                mins = int(self.sim_time % 60)
                trains_in_siding = sum(1 for t in self.active_trains if t.is_in_siding)
                
                time_str = f"Dia {days} | {hours:02d}:{mins:02d}"
                msg = debug_font.render(f"{time_str} | Trens: {len(self.active_trains)} | Apartats: {trains_in_siding}", True, (0,0,0))
                self.screen.blit(msg, (10, 10))
                
                pygame.display.flip()
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.brain.save_table("q_table.pkl")
            self.generate_report()
            pygame.quit()
            print("Simulació finalitzada.")

    def generate_report(self):
        filename = "simulation_report.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("=================================================================\n")
                f.write("                RODALIES AI - FINAL SIMULATION REPORT            \n")
                f.write("=================================================================\n")
                f.write(f"Total Completed Trains: {len(self.completed_trains_log)}\n")
                f.write(f"Simulation Time Ended:  {self.sim_time:.2f} min\n")
                f.write(f"Siding Uses (Apartaderos): {self.siding_usage_count}\n")
                
                siding_stations = [n for n in self.nodes.values() if n.has_siding]
                if siding_stations:
                    f.write(f"\nStations with Sidings:\n")
                    for station in siding_stations:
                        f.write(f"  - {station.name} (ID: {station.id})\n")
                f.write("\n")
                
                header = f"{'ID':<8} | {'ROUTE':<45} | {'DELAY (min)':<12} | {'STATUS'}\n"
                f.write(header)
                f.write("-" * len(header) + "\n")
                
                for entry in self.completed_trains_log:
                    route_str = f"{entry['origin']} -> {entry['dest']}"
                    if len(route_str) > 44: route_str = route_str[:41] + "..."
                    delay_val = entry['delay']
                    line = f"{entry['id']:<8} | {route_str:<45} | {delay_val:<12.2f} | {entry['status']}\n"
                    f.write(line)

                if self.completed_trains_log:
                    f.write("=================================================================\n")
                    f.write("                        GENERAL STATISTICS                        \n")
                    f.write("=================================================================\n")
                    total_delay = sum(max(0.0, entry['delay']) for entry in self.completed_trains_log)
                    avg_delay = total_delay / len(self.completed_trains_log)
                    f.write("\n")
                    f.write(f"Average Delay (only delays >= 0): {avg_delay:.2f} min\n")
                    f.write(f"Total trains with delays: {sum(1 for entry in self.completed_trains_log if entry['delay'] >= 0.0)}\n")
                    f.write(f"Eficiency Rate: {100.0 * sum(1 for entry in self.completed_trains_log if entry['status'] == 'ON TIME') / len(self.completed_trains_log):.2f}%\n")
                    f.write("=================================================================\n")
                else:
                    f.write("\nNo trains completed the simulation.\n")

            print(f"\n📄 [SUCCESS] Report generated: {filename}")
        except Exception as e:
            print(f"Could not save report: {e}")

if __name__ == "__main__":
    RodaliesAI().run()