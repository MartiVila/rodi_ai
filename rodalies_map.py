from scraper_oneuse import scrape_rodalies_line_stations
import pandas as panda
import numpy as np
import networkx as nx
import math
import matplotlib.pyplot as plt
import re
import unicodedata
import folium
import osmnx as ox
from geopy.distance import great_circle

#TODO: REPASSAR AIXÒ
ox.settings.log_console = True
ox.settings.use_cache = True
ox.settings.timeout = 900 #timeout of 900 seconds if the download crashes

def _normalize_name(name):
    '''
    This funciton is made to normalize the station names to be able to match them properly
    The normaliztion may be overprovident but we want to ensure the names are properly matched
    cause the source of Renfe Data isn't consistent at all.
    '''
    #Normaliztion of all the names from csv, to upper, no accents, no special characters neither spaces
    normalized_name = name.lower()
    normalized_name = normalized_name.replace(' ', '')
    normalized_name = normalized_name.replace('-', '')
    normalized_name = normalized_name.replace("'", '')

    normalized_name = normalized_name.replace('ñ', 'n')

    normalized_name = normalized_name.replace('ç', 'c')
    
    normalized_name = unicodedata.normalize('NFD', normalized_name)
    #this line is to ensure al the accents are removes, becoming their stadnard letter with the NFD decoding
    
    final_name = "".join(
        c for c in normalized_name 
        if unicodedata.category(c) != 'Mn' #Removing accents again
    )

    final_name = final_name.upper()#everything must be upper
    return final_name

file_path = 'data/estaciones_coordenadas.csv'
#We're reading with two separtors cause the file is big and we don't trust renfe!
def read_data(path):
    try:
        #First we try to read it with ;, which would be the correct separator in this case
        return panda.read_csv(path, sep=';', encoding='latin1')
    except Exception:
        pass
    try:
        #In case a concret line is not separeted with ;
        return panda.read_csv(path, sep=',', encoding='latin1')
    except Exception:
        pass
    try:
        return panda.read_csv(path, sep=';')
    except Exception:
        return panda.read_csv(path, sep=',')

data = read_data(file_path)
data.columns = [col.upper().strip().replace('Ó', 'O') for col in data.columns] #NO SE QUE POLLES FA AIXO AQUI, SI HO TREUS NO FUNCIONA PERO NO CALDRIA FER AQUI AQUESTA NORMALITZACIO

#Helper to parse malformed coordinate strings found in the CSV.
def _parse_coord(raw, is_lat=True):
    '''
    This function is made to parse malformed coordinate strings found in the CSV.
    We found the source of the document wasn't relaible, so we had to ensure the proper structure of the data
    is_lat indicates if we are parsing a latitude (True) or longitude (False), also becuase of the difference between data sources
    '''
    #Handle explicit missing or NaN values 
    if raw is None or (isinstance(raw, (float, np.floating)) and (np.isnan(raw) or math.isnan(raw))):
        return None

    #We get the string and strip it
    s = str(raw).strip()
    if not s:
        return None

    s = s.replace('−', '-')

    #We have stablished that the coordinates are in europe format, so commas are decimals
    #and a 2 attempts method toprevent errors we had previosult
    try:
        if '.' in s and ',' in s:
            #Decide decimal separator by last occurrence
            if s.rfind(',') > s.rfind('.'):
                #commas are decimals, dots thousands
                candidate = s.replace('.', '').replace(',', '.')
            else:
                candidate = s.replace(',', '')
        else:
            candidate = s.replace(',', '.')
        
        v = float(candidate)
        if is_lat and 30.0 <= v <= 50.0:
            return float(v)
        if (not is_lat) and -20.0 <= v <= 20.0:
            return float(v)
    except Exception:
        pass

    
    '''
    THis second attempt is allwatys used
    The prinicple is to get a integer with all the coordinates, after this it is devided by various multiples od 10,
    and the code takes the most probable candidate based on ranges
    '''
    cleaned_digits = re.sub(r"[^0-9-]", "", s)
    if cleaned_digits in ("", "-"):
        return None

    try:
        n = int(cleaned_digits)
    except Exception:
        return None

    divisors = [1, 10, 100, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]
    candidates = [n / d for d in divisors]

    #Strict ranges chosen for Barcelona area, this was made to prevent an error where half the coordinates were pointing Italy
    if is_lat:
        strict_min, strict_max, expected = 30.0, 50.0, 41.38
    else:
        strict_min, strict_max, expected = -10.0, 10.0, 2.16

    strict_hits = [c for c in candidates if strict_min <= c <= strict_max]
    if strict_hits:
        return float(min(strict_hits, key=lambda x: abs(x - expected)))
    
    if is_lat:
        broad_min, broad_max = -90.0, 90.0
    else:
        broad_min, broad_max = -180.0, 180.0

    broad_hits = [c for c in candidates if broad_min <= c <= broad_max]
    if broad_hits:
        return float(min(broad_hits, key=lambda x: abs(x - expected)))

    return None

#Cleaning an normalitzing latitude and longitude columns
data['LATITUD'] = data.get('LATITUD').apply(lambda v: _parse_coord(v, is_lat=True))
data['LONGITUD'] = data.get('LONGITUD').apply(lambda v: _parse_coord(v, is_lat=False))


#The data of the coordinates is beign used in different formats, 
#so we store the rail network graph globally to avoid re-downloading or re-projecting it multiple times.
RAIL_NETWORK_GRAPH_WGS = None #this one is in greograpgical coordinates
RAIL_NETWORK_GRAPH_PROJ = None #this one is projected coordinates

def get_rail_distance(lat1, lon1, lat2, lon2, rail_graph_wgs):
    """
    This function is due to calculate the rail distance between two stations
    In a way were using the Harvesine distance between all the rail_nodes between two stations

    We got a graph with all the medium nodes so now we just need to find where are the stations, and all the node between 2 stations will
    be used to calculate the distance.

    There may be some error in the caclution, cause of the use of the Haversine function, but it should be minimal.
    """

    if None in [lat1, lon1, lat2, lon2] or any(isinstance(x, float) and math.isnan(x) for x in [lat1, lon1, lat2, lon2]):
        return 9999.0

    try:
        sample_node = next(iter(rail_graph_wgs.nodes))
        sample_cord = rail_graph_wgs.nodes[sample_node]
        sample_x = sample_cord.get('x', sample_cord.get('lon', None))
        sample_y = sample_cord.get('y', sample_cord.get('lat', None))
        if sample_x is None or sample_y is None:
            print("ERROR: Somme coordinates are missing")
        else:
            if not (-90.0 <= sample_y <= 90.0 and -180.0 <= sample_x <= 180.0):
                print("ERROR: rail_graph appears to IS projected with cartessian coordinates not geographical.")
                print("  sample_x, sample_y:", sample_x, sample_y)
    except StopIteration:
        print("ERROR: Rail graph empty")
        return great_circle((lat1, lon1), (lat2, lon2)).km
    


    try:
        #we look for teh nearest node, and we calculate the shortest path between them
        orig_node = ox.nearest_nodes(rail_graph_wgs, lon1, lat1)
        dest_node = ox.nearest_nodes(rail_graph_wgs, lon2, lat2)

        #we use weight='length' when available to prefer realistic rail routing:
        try:
            shortest_path = ox.shortest_path(rail_graph_wgs, orig_node, dest_node, weight='length')
        except Exception:
            shortest_path = ox.shortest_path(rail_graph_wgs, orig_node, dest_node)

        if shortest_path is None or len(shortest_path) == 0:
            print(f"No path between {orig_node} and {dest_node}")
            return great_circle((lat1, lon1), (lat2, lon2)).km

        #If orig==dest or path of length 1, fallback
        if orig_node == dest_node or len(shortest_path) <= 1:
            return great_circle((lat1, lon1), (lat2, lon2)).km

        total_km = 0.0
        for u, v in zip(shortest_path[:-1], shortest_path[1:]):
            node_u = rail_graph_wgs.nodes[u]
            node_v = rail_graph_wgs.nodes[v]

            #Get lat/lon robustly
            lon_u = node_u.get('x', node_u.get('lon', None))
            lat_u = node_u.get('y', node_u.get('lat', None))
            lon_v = node_v.get('x', node_v.get('lon', None))
            lat_v = node_v.get('y', node_v.get('lat', None))

            #If any of these are None, abort and fallback
            if None in (lat_u, lon_u, lat_v, lon_v):
                print(f"Missing coords for nodes {u} or {v}, PITOOOOOO")
                return great_circle((lat1, lon1), (lat2, lon2)).km

            if not (-90 <= lat_u <= 90 and -90 <= lat_v <= 90 and -180 <= lon_u <= 180 and -180 <= lon_v <= 180):
                print(f"Coords look projected for nodes {u}/{v}: {(lon_u, lat_u)} -> {(lon_v, lat_v)}")
                print("Falling back to great_circle on station coords.")
                return great_circle((lat1, lon1), (lat2, lon2)).km

            total_km += great_circle((lat_u, lon_u), (lat_v, lon_v)).km

        print(f"Total distance via nodes: {total_km:.4f} km")
        if total_km < 0.05:
            print("total < 0.05km impossible")
        return total_km

    except Exception as e:
        print(f"EERROR: calculating geographic rail distance: {e}. Falling back to great_circle.")
        return great_circle((lat1, lon1), (lat2, lon2)).km


print("Data shape:", data.shape)
print(data.head())

G = nx.Graph()

print("Starting node addition...")

for index, row in data.iterrows():
    station_id = row.get('ID')
    station_name = row.get('NOMBRE_ESTACION')
    lat = row.get('LATITUD')
    lon = row.get('LONGITUD')

    norm_name = _normalize_name(station_name)
    print(f"Processing station: Name={norm_name}")

    #Add node keyed by normalized name, even if coordinates are invalid.
    G.add_node(norm_name, id=station_id, name=station_name, lat=lat, lon=lon)

print(f"Finished adding {G.number_of_nodes()} stations as nodes.")

'''
Downloaf all the cache files, with the rail_nodes information
'''
PLACE_NAME = "Catalonia, Spain" 

print(f"Downloading rail network data for {PLACE_NAME} (Timeout set to 15 mins)...")

try:
    rail_graph_wgs = ox.graph_from_place(PLACE_NAME, network_type='all', retain_all=False,  custom_filter='["railway"~"rail|station|subway|light_rail"]')
    #keep WGS graph for nearest_nodes and Haversine calculations
    RAIL_NETWORK_GRAPH_WGS = rail_graph_wgs
    try:
        RAIL_NETWORK_GRAPH_PROJ = ox.project_graph(rail_graph_wgs)
    except Exception as e:
        RAIL_NETWORK_GRAPH_PROJ = None
        print("Could not project graph (non-fatal):", e)

    print(" Download completed.")

#WE SHOULD NEVER GET INTO AN EXCEPTION HERE BUT JUST IN CASE
except Exception as e:
    print(f" Failed downloafidns: {e}")
    print("❌ Cannot download rail network: Insufficient valid station coordinates for BBox.")
    RAIL_NETWORK_GRAPH_WGS = None
    RAIL_NETWORK_GRAPH_PROJ = None
        
    
#debug of teh downaloaded data
if RAIL_NETWORK_GRAPH_WGS is not None:
    crs = RAIL_NETWORK_GRAPH_WGS.graph.get('crs')
    print("Rail graph", crs)
    try:
        sample_node = next(iter(RAIL_NETWORK_GRAPH_WGS.nodes))
        print("Sample node attrs:", RAIL_NETWORK_GRAPH_WGS.nodes[sample_node])
    except Exception as e:
        print("Could not inspect sample node:", e)

def add_rail_connections(graph: nx.Graph, connections: list, rail_graph_wgs: nx.MultiDiGraph):
    """
    Adds the connection between all the nodes
    the graph is created and filled with all the stations, this function will add the edges
    the edges have the two nodes and the distance in the parameters
    """
    added_edges_count = 0 #to keep track of the number of edges added
    _norm_conn_name = _normalize_name 

    for station1, station2 in connections:
        n1 = _norm_conn_name(station1)
        n2 = _norm_conn_name(station2)
        
        #Check if both normalized station names exist in the graph, important to debug
        if n1 in graph and n2 in graph:
            lat1, lon1 = graph.nodes[n1]['lat'], graph.nodes[n1]['lon']
            lat2, lon2 = graph.nodes[n2]['lat'], graph.nodes[n2]['lon']
            
            
            #Calculate the rail track distance
            if rail_graph_wgs:
                distance = get_rail_distance(lat1, lon1, lat2, lon2, rail_graph_wgs)
            else:
                print("Damn that's some thought shit man, I don't know what to do right now.")
            
            #only distance =0 when is a junction of the nodes
            if distance > 0:
                graph.add_edge(n1, n2, distance_km=distance)
                added_edges_count += 1
                #TODO: JO PER MI QUE TOT AIXO ES POT TREURE ESTA FICAT PER FERE COMPROVACIONS PERO NO CAL
            else:
                #add the edge if a physical connection is implied by the Rodalies list, 
                 if n1 != n2:
                     graph.add_edge(n1, n2, distance_km=0.01) #use a very small distance
                     added_edges_count += 1
        else:
            #edbug
            print(f"Warning: Station '{station1}' (norm '{n1}') or '{station2}' (norm '{n2}') not found in the graph.")
            
    print(f"Successfully added {added_edges_count} edges from the connection list.")
    return graph

#Odio la renfe tio, mireu que he hagut de fer perque la renfe no sap escriure be les estacions
r1_connections = [
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
];
r2_connections = [
    ('CASTELLDEFELS', 'GAVA'),
    ('GAVA', 'VILADECANS'),
    ('VILADECANS', 'ELPRATDELLOBREGAT'),
    ('ELPRATDELLOBREGAT', 'BELLVITGE'),
    ('BELLVITGE', 'BARCELONASANTS'),
    ('BARCELONASANTS', 'BARCELONAPASSEIGDEGRACIA'),
    ('BARCELONAPASSEIGDEGRACIA', 'BARCELONACLOTARAGO'),
    ('BARCELONACLOTARAGO', 'BARCELONASANTANDREUCOMTAL'),
    ('BARCELONASANTANDREUCOMTAL', 'MONTCADAIREIXAC'),
    ('MONTCADAIREIXAC', 'LALLAGOSTA'),
    ('LALLAGOSTA', 'MOLLETSANTFOST'),
    ('MOLLETSANTFOST', 'MONTMELO'),
    ('MONTMELO', 'GRANOLLERSCENTRE')
];
r2N_connections = [
    ('AEROPORT', 'ELPRATDELLOBREGAT'),
    ('ELPRATDELLOBREGAT', 'BELLVITGE'),
    ('BELLVITGE', 'BARCELONASANTS'),
    ('BARCELONASANTS', 'BARCELONAPASSEIGDEGRACIA'),
    ('BARCELONAPASSEIGDEGRACIA', 'BARCELONACLOTARAGO'),
    ('BARCELONACLOTARAGO', 'BARCELONASANTANDREUCOMTAL'),
    ('BARCELONASANTANDREUCOMTAL', 'MONTCADAIREIXAC'),
    ('MONTCADAIREIXAC', 'LALLAGOSTA'),
    ('LALLAGOSTA', 'MOLLETSANTFOST'),
    ('MOLLETSANTFOST', 'MONTMELO'),
    ('MONTMELO', 'GRANOLLERSCENTRE'),
    ('GRANOLLERSCENTRE', 'LESFRANQUESESGRANOLLERSNORD'),
    ('LESFRANQUESESGRANOLLERSNORD', 'CARDEDEU'),
    ('CARDEDEU', 'LLINARSDELVALLES'),
    ('LLINARSDELVALLES', 'PALAUTORDERA'),
    ('PALAUTORDERA', 'SANTCELONI'),
    ('SANTCELONI', 'GUALBA'),
    ('GUALBA', 'RIELLSIVIABREABREDA'),
    ('RIELLSIVIABREABREDA', 'HOSTALRIC'),
    ('HOSTALRIC', 'MACANETMASSANES')
];
r2S_connections = [
    ('SANTVICENCDECALDERS', 'CALAFELL'),
    ('CALAFELL', 'SEGURDECALAFELL'),
    ('SEGURDECALAFELL', 'CUNIT'),
    ('CUNIT', 'CUBELLES'),
    ('CUBELLES', 'VILANOVAILAGELTRU'),
    ('VILANOVAILAGELTRU', 'SITGES'),
    ('SITGES', 'GARRAF'),
    ('GARRAF', 'PLATJADECASTELLDEFELS'),
    ('PLATJADECASTELLDEFELS', 'CASTELLDEFELS'),
    ('CASTELLDEFELS', 'GAVA'),
    ('GAVA', 'VILADECANS'),
    ('VILADECANS', 'ELPRATDELLOBREGAT'),
    ('ELPRATDELLOBREGAT', 'BELLVITGE'),
    ('BELLVITGE', 'BARCELONASANTS'),
    ('BARCELONASANTS', 'BARCELONAPASSEIGDEGRACIA'),
    ('BARCELONAPASSEIGDEGRACIA', 'BARCELONAESTACIODEFRANCA')
];
r3_connections = [
    ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'),
    ('BARCELONASANTS', 'PLACADECATALUNYA'),
    ('PLACADECATALUNYA', 'ARCDETRIOMF'),
    ('ARCDETRIOMF', 'LASAGRERAMERIDIANA'),
    ('LASAGRERAMERIDIANA', 'BARCELONAFABRAIPUIG'),
    ('BARCELONAFABRAIPUIG', 'TORREDELBARO'),
    ('TORREDELBARO', 'MONTCADABIFURCACIO'),
    ('MONTCADABIFURCACIO', 'MONTCADARIPOLLET'),
    ('MONTCADARIPOLLET', 'SANTAPERPETUADEMOGODA'),
    ('SANTAPERPETUADEMOGODA', 'MOLLETSANTAROSA'),
    ('MOLLETSANTAROSA', 'PARETSDELVALLES'),
    ('PARETSDELVALLES', 'GRANOLLERSCANOVELLES'),
    ('GRANOLLERSCANOVELLES', 'LESFRANQUESESDELVALLES'),
    ('LESFRANQUESESDELVALLES', 'LAGARRIGA'),
    ('LAGARRIGA', 'FIGARO'),
    ('FIGARO', 'SANTMARTIDECENTELLES'),
    ('SANTMARTIDECENTELLES', 'CENTELLES'),
    ('CENTELLES', 'BALENYAELSHOSTALETS'),
    ('BALENYAELSHOSTALETS', 'BALENYATONASEVA'),
    ('BALENYATONASEVA', 'VIC'),
    ('VIC', 'MANLLEU'),
    ('MANLLEU', 'TORELLO'),
    ('TORELLO', 'BORGONYA'),
    ('BORGONYA', 'SANTQUIRZEDEBESORAMONTESQUIU'),
    #No hi poden haver mes estacions ens tanquem nomes aservei de rodalies no regionals a la llista cv estan n ho entenc pero els posem igualment
    ('SANTQUIRZEDEBESORAMONTESQUIU', 'LAFARGADEBEBIE'),
    ('LAFARGADEBEBIE', 'RIPOLL'),
    ('RIPOLL', 'CAMPDEVANOL'),
    ('CAMPDEVANOL', 'RIBESDEFRESER'),
    ('RIBESDEFRESER', 'PLANOLES'), 
    ('PLANOLES', 'TOSES'),
    ('TOSES', 'LAMOLINA'),
    ('LAMOLINA', 'URTXALP'),
    ('URTXALP', 'PUIGCERDA'), 
];
r4_connections = [
    ('SANTVICENCDECALDERS', 'ELVENDRELL'),
    ('ELVENDRELL', 'LARBOC'),
    ('LARBOC', 'ELSMONJOS'),
    ('ELSMONJOS', 'VILAFRANCADELPENEDES'),
    ('VILAFRANCADELPENEDES', 'LAGRANADA'),
    ('LAGRANADA', 'LAVERNSUBIRATS'),
    ('LAVERNSUBIRATS', 'SANTSADURNIDANOIA'),
    ('SANTSADURNIDANOIA', 'GELIDA'),
    ('GELIDA', 'MARTORELL'),
    ('MARTORELL', 'CASTELLBISBAL'),
    ('CASTELLBISBAL', 'ELPAPIOL'),
    ('ELPAPIOL', 'MOLINSDEREI'), 
    ('MOLINSDEREI', 'SANTFELIUDELLOBREGAT'),
    ('SANTFELIUDELLOBREGAT', 'SANTJOANDESPI'),
    ('SANTJOANDESPI', 'CORNELLA'),
    ('CORNELLA', 'LHOSPITALETDELLOBREGAT'),
    ('LHOSPITALETDELLOBREGAT', 'BARCELONASANTS'),
    ('BARCELONASANTS', 'PLACADECATALUNYA'),
    ('PLACADECATALUNYA', 'ARCDETRIOMF'),
    ('ARCDETRIOMF', 'LASAGRERAMERIDIANA'),
    ('LASAGRERAMERIDIANA', 'BARCELONAFABRAIPUIG'),
    ('BARCELONAFABRAIPUIG', 'TORREDELBARO'),
    ('TORREDELBARO', 'MONTCADABIFURCACIO'),
    ('MONTCADABIFURCACIO', 'MONTCADAIREIXACMANRESA'),
    ('MONTCADAIREIXACMANRESA', 'MONTCADAIREIXACSANTAMARIA'),
    ('MONTCADAIREIXACSANTAMARIA', 'CERDANYOLADELVALLES'),
    ('CERDANYOLADELVALLES', 'BARBERADELVALLES'),
    ('BARBERADELVALLES', 'SABADELLSUD'),
    ('SABADELLSUD', 'SABADELLCENTRE'),
    ('SABADELLCENTRE', 'SABADELLNORD'),
    ('SABADELLNORD', 'TERRASSAEST'),
    ('TERRASSAEST', 'TERRASSA'),
    ('TERRASSA', 'SANTMIQUELDEGONTERES'),
    ('SANTMIQUELDEGONTERES', 'VILADECAVALLS'),
    ('VILADECAVALLS', 'VACARISSESTORREBLANCA'),
    ('VACARISSESTORREBLANCA', 'VACARISSES'),
    ('VACARISSES', 'CASTELLBELLIELVILARMONISTROLDEMONTSERRAT'),
    ('CASTELLBELLIELVILARMONISTROLDEMONTSERRAT', 'SANTVICENCDECASTELLET'),
    ('SANTVICENCDECASTELLET', 'MANRESA')
];
r7_connections = [
    ('BARCELONAFABRAIPUIG', 'TORREDELBARO'),
    ('TORREDELBARO', 'MONTCADABIFURCACIO'),
    ('MONTCADABIFURCACIO', 'MONTCADAIREIXACMANRESA'),
    ('MONTCADAIREIXACMANRESA', 'MONTCADAIREIXACSANTAMARIA'),
    ('MONTCADAIREIXACSANTAMARIA', 'CERDANYOLADELVALLES'),
    ('CERDANYOLADELVALLES', 'CERDANYOLAUNIVERSITAT')
];
r8_connections = [
    ('MARTORELL', 'CASTELLBISBAL'),
    ('CASTELLBISBAL', 'RUBI'),
    ('RUBI', 'SANTCUGATDELVALLES'),
    ('SANTCUGATDELVALLES', 'CERDANYOLAUNIVERSITAT'),
    ('CERDANYOLAUNIVERSITAT', 'SANTAPERPETUADEMOGODA'),
    ('SANTAPERPETUADEMOGODA', 'MOLLETSANTFOST'),
    ('MOLLETSANTFOST', 'MONTMELO'),
    ('MONTMELO', 'GRANOLLERSCENTRE')
]

G = add_rail_connections(G, r1_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r2_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r2N_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r2S_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r3_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r4_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r7_connections, RAIL_NETWORK_GRAPH_WGS)
G = add_rail_connections(G, r8_connections, RAIL_NETWORK_GRAPH_WGS)

print(f"Number of nodes (stations): {G.number_of_nodes()}")
print(f"Number of edges (connections): {G.number_of_edges()}")

print("Nodes and example attributes (ID included):")
for i, node in enumerate(list(G.nodes)[:3]):
    print(f"Node: {node}, Attribute: {G.nodes[node]}")

print("Edges and their example attributes:")
for i, edge in enumerate(list(G.edges(data=True))[:3]):
    print(f"Edge: {edge[0]} -> {edge[1]}, Attributes: {edge[2]}")


def visualize_rail_graph(graph: nx.Graph, output_filename="rodalies_map.html"):
    """
    using the folium library to create an interactive map of the rail network.
    This map will display stations as markers and connections as lines.
    """
        
    #Collect valid coordinates from the graph
    latitudes = [data['lat'] for _, data in graph.nodes(data=True)
                 if data.get('lat') is not None and not (isinstance(data.get('lat'), float) and math.isnan(data.get('lat')))]
    longitudes = [data['lon'] for _, data in graph.nodes(data=True)
                 if data.get('lon') is not None and not (isinstance(data.get('lon'), float) and math.isnan(data.get('lon')))]

    if not latitudes or not longitudes:
        print("Error: No valid coordinates found to create a geographic map.")
        return

    max_lat = float(np.max(latitudes))
    max_lon = float(np.max(longitudes))
    min_lat = float(np.min(latitudes))
    min_lon = float(np.min(longitudes))

    m = folium.Map(location=[(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom_start=8, tiles=None)

    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    folium.TileLayer('CartoDB Positron', name='CartoDB Positro n').add_to(m)

    orm_tiles = 'https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png'
    folium.TileLayer(tiles=orm_tiles, attr='OpenRailwayMap', name='OpenRailwayMap', overlay=True, control=True).add_to(m)
    
    
    station_group = folium.FeatureGroup(name="Rodalies Stations").add_to(m)
    
    #adding the nodes
    for node_name, data in graph.nodes(data=True):
        lat = data.get('lat')
        lon = data.get('lon')
        original_name = data.get('name') # Assuming 'name' holds the original station name

        if lat is not None and lon is not None and not math.isnan(lat):
            #Create a Marker for each station. Popup shows the station name
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color='#2b7bba',
                fill=True,
                fill_color='#2b7bba',
                fill_opacity=0.9,
                popup=f"<b>{original_name}</b><br>ID: {data.get('id')}"
            ).add_to(station_group)

    #Use a separate FeatureGroup for lines
    line_group = folium.FeatureGroup(name="Rail Connections").add_to(m)

    for u, v, edge_data in graph.edges(data=True):
        lat_u, lon_u = graph.nodes[u].get('lat'), graph.nodes[u].get('lon')
        lat_v, lon_v = graph.nodes[v].get('lat'), graph.nodes[v].get('lon')
        distance = edge_data.get('distance_km', None)

        #Ensure coordinates are valid numbers
        if None not in (lat_u, lon_u, lat_v, lon_v) and not any(isinstance(c, float) and math.isnan(c) for c in (lat_u, lon_u, lat_v, lon_v)):
            points = [(lat_u, lon_u), (lat_v, lon_v)]
            tooltip = f"Tram: {u} - {v}"
            if distance is not None and isinstance(distance, (int, float)):
                tooltip += f" Rail Distance: {distance:.2f} km"
            folium.PolyLine(
                points,
                color='gray',
                weight=1.5,
                opacity=0.8,
                tooltip=tooltip
            ).add_to(line_group)

    folium.LayerControl().add_to(m)

    #Fit map to bounds of all stations so the background covers Catalunya/area of interest
    bounds = [[min_lat, min_lon], [max_lat, max_lon]]
    m.fit_bounds(bounds, padding=(50, 50))

    m.save(output_filename)
    print(f"map saved to: {output_filename}")

if __name__ == "__main__":
    visualize_rail_graph(G)
