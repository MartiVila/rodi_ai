import pygame
import sys
import math
import random
import pandas as pd
import requests
import re
import unicodedata
from enum import Enum
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# 1. ESTRUCTURA DE NODES I ARESTES (Basada en simulator.py)
# ==============================================================================

class EdgeType(Enum):
    NORMAL = 1
    OBSTACLE = 2

class Node:
    def __init__(self, x, y, node_id):
        self.x = x
        self.y = y
        self.id = node_id
        self.radius = 4  # Més petit per veure tot el mapa
        # Atributs addicionals per dades reals
        self.lat = None
        self.lon = None
        self.real_name = ""

    def draw(self, screen):
        # Dibuixem el node
        pygame.draw.circle(screen, (0, 100, 200), (int(self.x), int(self.y)), self.radius)
        
        # Només dibuixem el nom si passem el ratolí per sobre (per no saturar)
        # O en aquest cas, simplificat: no dibuixem text per defecte per rendiment en mapes grans
        # Si té l'atribut 'highlight', el mostrem
        if hasattr(self, 'highlight') and self.highlight:
            font = pygame.font.SysFont("Arial", 16, bold=True)
            text = font.render(str(self.real_name), True, (50, 50, 50))
            # Fons blanc pel text
            bg_rect = text.get_rect(center=(self.x, self.y - 15))
            pygame.draw.rect(screen, (255, 255, 255), bg_rect)
            screen.blit(text, bg_rect)

class Edge:
    def __init__(self, node1, node2, edge_type, duration_seconds):
        self.node1 = node1
        self.node2 = node2
        self.edge_type = edge_type
        
        # Guardem la duració real en segons (pes de l'aresta)
        self.duration = duration_seconds 
        
        # Velocitat visual per a la simulació (opcional: podem fer que depengui del temps)
        # Si triga més, la velocitat visual (step) hauria de ser més petita.
        # Per exemple: 1.0 / duration_seconds
        self.speed = 1.0 / max(duration_seconds, 1) 

    def draw(self, screen):
        # Dibuix visual (mateix codi que abans, potser ajustant colors si vols diferenciar vies)
        color = (100, 100, 100) if self.edge_type == EdgeType.NORMAL else (200, 50, 50)
        
        # Offset visual per no pintar les 4 línies una sobre l'altra
        # Calculem un petit desplaçament segons si és via 1 o via 2
        # (Aquesta lògica d'offset visual pot ser complexa, aquí en poso una de simple)
        pygame.draw.line(screen, color, (self.node1.x, self.node1.y), (self.node2.x, self.node2.y), 2)

class Train:
    def __init__(self, start_node, end_node, edge):
        self.start_node = start_node
        self.end_node = end_node
        self.edge = edge
        self.progress = 0
        self.speed = edge.speed / 100

    def update(self):
        self.progress += self.speed
        if self.progress >= 1:
            self.progress = 1

    def draw(self, screen):
        x = self.start_node.x + (self.end_node.x - self.start_node.x) * self.progress
        y = self.start_node.y + (self.end_node.y - self.start_node.y) * self.progress
        pygame.draw.circle(screen, (255, 200, 0), (int(x), int(y)), 6)

    def is_finished(self):
        return self.progress >= 1

# ==============================================================================
# 2. LÒGICA DE CÀRREGA DE DADES REALS I SIMULADOR
# ==============================================================================

class RodaliesMap:
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rodalies Network - Real Data Visualization")
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.nodes: Dict[str, Node] = {} # Map de nom_normalitzat -> Node
        self.all_edges: List[Edge] = []
        
        # Carregar dades
        print("Carregant dades...")
        self.load_real_data()
        print(f"Graf construït: {len(self.nodes)} estacions, {len(self.all_edges)} connexions.")

    def _normalize_name(self, name: str) -> str:
        if not isinstance(name, str): return ""
        n = name.lower().replace(' ', '').replace('-', '').replace("'", "")
        n = n.replace('ñ', 'n').replace('ç', 'c')
        n = unicodedata.normalize('NFD', n)
        n = "".join(c for c in n if unicodedata.category(c) != 'Mn')
        return n.upper()

    def _parse_coord(self, raw, is_lat=True):
        """Neteja coordenades malmeses del CSV (Ex: 413.038 -> 41.3038)."""
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            return None
        s = str(raw).strip().replace('−', '-')
        if not s: return None
        
        # Eliminar caràcters estranys excepte dígits i signe menys
        digits = re.sub(r"[^0-9-]", "", s)
        try:
            val_int = int(digits)
            # Heurística: provar divisors per caure en el rang de Catalunya
            target = 41.5 if is_lat else 2.0
            valid_range = (39.0, 44.0) if is_lat else (-1.0, 5.0)
            
            divisors = [10**i for i in range(10)]
            candidates = [val_int / d for d in divisors]
            hits = [c for c in candidates if valid_range[0] <= c <= valid_range[1]]
            
            if hits:
                return float(min(hits, key=lambda x: abs(x - target)))
        except:
            pass
        return None

    def load_real_data(self):
        # 1. Llegir CSV amb gestió d'espais
        csv_path = 'data/estaciones_coordenadas.csv'
        try:
            # skipinitialspace=True ajuda si hi ha espais després del punt i coma
            df = pd.read_csv(csv_path, sep=';', encoding='latin1', skipinitialspace=True)
            
            # NETEJA CRÍTICA: Eliminem espais en blanc dels noms de les columnes i ho passem a majúscules
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Comprovació de seguretat
            if 'NOMBRE_ESTACION' not in df.columns:
                print(f"Alerta: Columnes trobades: {df.columns}")
                # Intent alternatiu amb coma
                df = pd.read_csv(csv_path, sep=',', encoding='latin1')
                df.columns = [c.strip().upper() for c in df.columns]

        except Exception as e:
            print(f"Error llegint CSV: {e}")
            return

        # 2. Processar Estacions
        temp_stations = []
        lats, lons = [], []

        for _, row in df.iterrows():
            # Ara accedim segurs perquè hem netejat les columnes
            name = row.get('NOMBRE_ESTACION')
            
            # Si encara falla, intentem buscar manualment la columna que contingui 'ESTACION'
            if pd.isna(name):
                col_name = next((c for c in df.columns if 'ESTACION' in c), None)
                if col_name:
                    name = row[col_name]
            
            if pd.isna(name): 
                continue
            
            norm_name = self._normalize_name(name)
            lat = self._parse_coord(row.get('LATITUD'), is_lat=True)
            lon = self._parse_coord(row.get('LONGITUD'), is_lat=False)
            
            if lat and lon:
                temp_stations.append({
                    'id': str(row.get('ID', '')), 
                    'norm': norm_name, 
                    'orig': name, # El nom original
                    'lat': lat, 
                    'lon': lon
                })
                lats.append(lat)
                lons.append(lon)

        if not lats: 
            print("No s'han trobat coordenades vàlides.")
            return

        # Calcular Bounding Box per escalar el mapa a la pantalla
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Padding del 5% perquè no quedin enganxats a la vora
        lat_pad = (max_lat - min_lat) * 0.05
        lon_pad = (max_lon - min_lon) * 0.05
        min_lat -= lat_pad; max_lat += lat_pad
        min_lon -= lon_pad; max_lon += lon_pad

        # 3. Crear Nodes
        for st in temp_stations:
            # Projecció simple a pantalla
            x = ((st['lon'] - min_lon) / (max_lon - min_lon)) * self.width
            y = self.height - ((st['lat'] - min_lat) / (max_lat - min_lat)) * self.height
            
            node = Node(x, y, st['id'])
            
            # ASSIGNACIÓ CLAU: Assignem 'name' perquè la classe Node del simulator.py el pugui dibuixar
            node.name = st['orig']  
            
            # Guardem lat/lon reals per si calgués
            node.lat = st['lat']
            node.lon = st['lon']
            
            self.nodes[st['norm']] = node
            
        #self.build_lines()
        self.build_R1()

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calcula distància en km entre dues coordenades."""
        R = 6371.0  # Radi de la Terra en km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = R * c
        return distance_km

    def add_connection(self, s1, s2):
        n1_key = self._normalize_name(s1)
        n2_key = self._normalize_name(s2)

        if n1_key in self.nodes and n2_key in self.nodes:
            node1 = self.nodes[n1_key]
            node2 = self.nodes[n2_key]

            # 1. Calcular distància real
            dist_km = self._haversine(node1.lat, node1.lon, node2.lat, node2.lon)
            if dist_km < 0.1: dist_km = 0.1 # Mínim de seguretat

            # 2. Calcular temps en segons (Suposant velocitat mitjana tren ~60 km/h)
            # Temps (h) = Distància (km) / Velocitat (km/h)
            # Temps (s) = Temps (h) * 3600
            AVG_SPEED_KMH = 60.0 
            duration_seconds = (dist_km / AVG_SPEED_KMH) * 3600
            
            # 3. Crear les 4 arestes (2 sentits x 2 vies)
            
            # --- Sentit A -> B ---
            # Via 1 (Normal)
            edge_ab_1 = Edge(node1, node2, EdgeType.NORMAL, duration_seconds)
            self.all_edges.append(edge_ab_1)
            
            # Via 2 (Pots fer-la tipus OBSTACLE o NORMAL segons vulguis)
            edge_ab_2 = Edge(node1, node2, EdgeType.NORMAL, duration_seconds) 
            self.all_edges.append(edge_ab_2)

            # --- Sentit B -> A ---
            # Via 1
            edge_ba_1 = Edge(node2, node1, EdgeType.NORMAL, duration_seconds)
            self.all_edges.append(edge_ba_1)
            
            # Via 2
            edge_ba_2 = Edge(node2, node1, EdgeType.NORMAL, duration_seconds)
            self.all_edges.append(edge_ba_2)

            # Opcional: Guardar referències al node si necessites navegar pel graf
            # node1.neighbors.append(edge_ab_1) ...

    def build_lines(self):
        # Definició de línies (com al codi anterior)
        lines = [
            # R1
            [('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'), ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
             ('SANTJOANDESPI', 'CORNELLA'), ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
             ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'), ('BARCELONASANTS', 'PLACADECATALUNYA'),
             ('PLACADECATALUNYA', 'ARCDETRIOMF'), ('ARCDETRIOMF', 'BARCELONACLOTARAGO'),
             ('BARCELONACLOTARAGO', 'SANTADRIADEBESOS'), ('SANTADRIADEBESOS', 'BADALONA'),
             ('BADALONA', 'MONTGAT'), ('MONTGAT', 'MONTGATNORD'), ('MONTGATNORD', 'ELMASNOU'),
             ('ELMASNOU', 'OCATA'), ('OCATA', 'PREMIADEMAR'), ('PREMIADEMAR', 'VILASSARDEMAR'),
             ('VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR'), ('CABRERADEMARVILASSARDEMAR', 'MATARO'),
             ('MATARO', 'SANTANDREUDELLAVANERES'), ('SANTANDREUDELLAVANERES', 'CALDESDESTRAC'),
             ('CALDESDESTRAC', 'ARENYSDEMAR'), ('ARENYSDEMAR', 'CANETDEMAR'),
             ('CANETDEMAR', 'SANTPOLDEMAR'), ('SANTPOLDEMAR', 'CALELLA'),
             ('CALELLA', 'PINEDADEMAR'), ('PINEDADEMAR', 'SANTASUSANNA'),
             ('SANTASUSANNA', 'MALGRATDEMAR'), ('MALGRATDEMAR', 'BLANES'),
             ('BLANES', 'TORDERA'), ('TORDERA', 'MACANETMASSANES')],

             
            # R2 / R2N / R2S (Simplificat)
            [('AEROPORT', 'ELPRATDELLOBREGAT'), ('ELPRATDELLOBREGAT', 'BELLVITGE'),
             ('BELLVITGE', 'BARCELONASANTS'), ('BARCELONASANTS', 'BARCELONAPASSEIGDEGRACIA'),
             ('BARCELONAPASSEIGDEGRACIA', 'BARCELONACLOTARAGO'), ('BARCELONACLOTARAGO', 'BARCELONASANTANDREUCOMTAL'),
             ('BARCELONASANTANDREUCOMTAL', 'MONTCADAIREIXAC'), ('MONTCADAIREIXAC', 'LALLAGOSTA'),
             ('LALLAGOSTA', 'MOLLETSANTFOST'), ('MOLLETSANTFOST', 'MONTMELO'),
             ('MONTMELO', 'GRANOLLERSCENTRE'), ('GRANOLLERSCENTRE', 'LESFRANQUESESGRANOLLERSNORD'),
             ('LESFRANQUESESGRANOLLERSNORD', 'CARDEDEU'), ('CARDEDEU', 'LLINARSDELVALLES'),
             ('LLINARSDELVALLES', 'PALAUTORDERA'), ('PALAUTORDERA', 'SANTCELONI'),
             ('SANTCELONI', 'GUALBA'), ('GUALBA', 'RIELLSIVIABREABREDA'),
             ('RIELLSIVIABREABREDA', 'HOSTALRIC'), ('HOSTALRIC', 'MACANETMASSANES'),
             ('SANTVICENCDECALDERS', 'CALAFELL'), ('CALAFELL', 'SEGURDECALAFELL'),
             ('SEGURDECALAFELL', 'CUNIT'), ('CUNIT', 'CUBELLES'), ('CUBELLES', 'VILANOVAILAGELTRU'),
             ('VILANOVAILAGELTRU', 'SITGES'), ('SITGES', 'GARRAF'), ('GARRAF', 'PLATJADECASTELLDEFELS'),
             ('PLATJADECASTELLDEFELS', 'CASTELLDEFELS'), ('CASTELLDEFELS', 'GAVA'), ('GAVA', 'VILADECANS'),
             ('VILADECANS', 'ELPRATDELLOBREGAT')],
             # R3, R4, R7, R8 (Es poden afegir la resta de llistes aquí, les incloc simplificades per espai)
             [('BARCELONAFABRAIPUIG', 'TORREDELBARO'), ('TORREDELBARO', 'MONTCADABIFURCACIO'),
              ('MONTCADABIFURCACIO', 'MONTCADAIREIXACMANRESA'), ('MONTCADAIREIXACMANRESA', 'MONTCADAIREIXACSANTAMARIA'),
              ('MONTCADAIREIXACSANTAMARIA', 'CERDANYOLADELVALLES'), ('CERDANYOLADELVALLES', 'CERDANYOLAUNIVERSITAT')]
        ]

        for line in lines:
            for s1, s2 in line:
                self.add_connection(s1, s2)


    def build_R1(self):
        # Definició de línies (com al codi anterior)
        lines = [
            # R1
            [('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'), ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
             ('SANTJOANDESPI', 'CORNELLA'), ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
             ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'), ('BARCELONASANTS', 'PLACADECATALUNYA'),
             ('PLACADECATALUNYA', 'ARCDETRIOMF'), ('ARCDETRIOMF', 'BARCELONACLOTARAGO'),
             ('BARCELONACLOTARAGO', 'SANTADRIADEBESOS'), ('SANTADRIADEBESOS', 'BADALONA'),
             ('BADALONA', 'MONTGAT'), ('MONTGAT', 'MONTGATNORD'), ('MONTGATNORD', 'ELMASNOU'),
             ('ELMASNOU', 'OCATA'), ('OCATA', 'PREMIADEMAR'), ('PREMIADEMAR', 'VILASSARDEMAR'),
             ('VILASSARDEMAR', 'CABRERADEMARVILASSARDEMAR'), ('CABRERADEMARVILASSARDEMAR', 'MATARO'),
             ('MATARO', 'SANTANDREUDELLAVANERES'), ('SANTANDREUDELLAVANERES', 'CALDESDESTRAC'),
             ('CALDESDESTRAC', 'ARENYSDEMAR'), ('ARENYSDEMAR', 'CANETDEMAR'),
             ('CANETDEMAR', 'SANTPOLDEMAR'), ('SANTPOLDEMAR', 'CALELLA'),
             ('CALELLA', 'PINEDADEMAR'), ('PINEDADEMAR', 'SANTASUSANNA'),
             ('SANTASUSANNA', 'MALGRATDEMAR'), ('MALGRATDEMAR', 'BLANES'),
             ('BLANES', 'TORDERA'), ('TORDERA', 'MACANETMASSANES')]
        ]

        for line in lines:
            for s1, s2 in line:
                self.add_connection(s1, s2)

    # --- MÈTODE SOL·LICITAT: GET_TRAINS ---
    def get_trains(self):
        """
        Obté la posició dels trens en temps real.
        Retorna una llista de diccionaris amb la informació.
        No s'utilitza automàticament en el bucle 'run', però està disponible.
        """
        url = "https://gtfsrt.renfe.com/vehicle_positions.json"
        trains = []
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for entity in data.get('entity', []):
                    v = entity.get('vehicle', {})
                    pos = v.get('position', {})
                    trains.append({
                        'id': v.get('id'),
                        'lat': pos.get('latitude'),
                        'lon': pos.get('longitude'),
                        'status': v.get('currentStatus'),
                        'tripId': v.get('trip', {}).get('tripId')
                    })
        except Exception as e:
            print(f"Error fetching trains: {e}")
        return trains

    # --- Bucle Principal de Pygame ---
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEMOTION:
                # Highlight node on hover
                mx, my = event.pos
                for node in self.nodes.values():
                    # Check distance
                    if math.sqrt((node.x - mx)**2 + (node.y - my)**2) < 10:
                        node.highlight = True
                    else:
                        node.highlight = False

    def draw(self):
        self.screen.fill((240, 240, 240)) # Fons gris clar
        
        # Dibuixar arestes
        for edge in self.all_edges:
            edge.draw(self.screen)
        
        # Dibuixar nodes
        for node in self.nodes.values():
            node.draw(self.screen)
            
        # Info
        font = pygame.font.SysFont("Arial", 14)
        text = font.render(f"Rodalies Simulator Map | Nodes: {len(self.nodes)} | Edges: {len(self.all_edges)}", True, (0,0,0))
        self.screen.blit(text, (10, 10))

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    sim = RodaliesMap()
    # Per provar el mètode get_trains sense executar-lo al loop:
    # print(sim.get_trains())
    sim.run()