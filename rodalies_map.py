from scraper_oneuse import scrape_rodalies_line_stations
import pandas as panda
import numpy as np
import networkx as nx
import math
import matplotlib.pyplot as plt
import re
import time
import random
import unicodedata
import folium


def _normalize_name(name):
    
    normalized_name = name.lower()
    #Remove special characters
    normalized_name = normalized_name.replace(' ', '')
    normalized_name = normalized_name.replace('-', '')
    normalized_name = normalized_name.replace("'", '')

    normalized_name = normalized_name.replace('ñ', 'n')

    normalized_name = normalized_name.replace('ç', 'c')
    
    #we're eliminatign the accents
    normalized_name = unicodedata.normalize('NFD', normalized_name)
    
    final_name = "".join(
        c for c in normalized_name 
        if unicodedata.category(c) != 'Mn'
    )

    final_name = final_name.upper()#everything must be upper
    return final_name

file_path = 'data/estaciones_coordenadas.csv'
#We're reading with two separtors cause the file is big and we don't trust renfe!
def read_data(path):
    try:
        return panda.read_csv(path, sep=';', encoding='latin1')
    except Exception:
        pass
    try:
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
    
    #Handle explicit missing / NaN values
    if raw is None or (isinstance(raw, (float, np.floating)) and (np.isnan(raw) or math.isnan(raw))):
        return None

    s = str(raw).strip()
    if not s:
        return None

    s = s.replace('\u2212', '-')

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

    #Attempt 2: Integer tokens scaled by powers of ten
    cleaned_digits = re.sub(r"[^0-9-]", "", s)
    if cleaned_digits in ("", "-"):
        return None

    try:
        n = int(cleaned_digits)
    except Exception:
        return None

    divisors = [1, 10, 100, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]
    candidates = [n / d for d in divisors]

    #Strict ranges chosen for Barcelona area (helps disambiguate scaling)
    if is_lat:
        strict_min, strict_max, expected = 30.0, 50.0, 41.38
    else:
        strict_min, strict_max, expected = -10.0, 10.0, 2.16

    strict_hits = [c for c in candidates if strict_min <= c <= strict_max]
    if strict_hits:
        return float(min(strict_hits, key=lambda x: abs(x - expected)))

    #Broader fallback (valid geographic bounds)
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


def haversine_distance(lat1, lon1, lat2, lon2):
    '''
    We did not found real information about the rails distance between stations, so we decdided
    to use the haversine formula to estimate the distance between two stations based on their coordinates.
    '''
    if None in [lat1, lon1, lat2, lon2] or any(math.isnan(x) for x in [lat1, lon1, lat2, lon2]):
        # Return a placeholder distance (e.g., 1 km) or raise an exception
        # Returning a placeholder allows the graph to form, but the cost is inaccurate.
        return 1.0 # Defaulting to 1 km if coordinates are missing/invalid
        
    R = 6371  # Earth's radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


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

    # Add node keyed by normalized name, even if coordinates are invalid.
    G.add_node(norm_name, id=station_id, name=station_name, lat=lat, lon=lon)

print(f"Finished adding {G.number_of_nodes()} stations as nodes.")


def add_rail_connections(graph: nx.Graph, connections: list):
    """
    Adds the connection between all the nodes
    the graph is created and filled with all the sattions, this function will add the edges
    the edges have the two nodes and the distacne in the parameters
    """
    added_edges_count = 0 #to keep track of the number of edges added
    #Use the unified normalization function
    _norm_conn_name = _normalize_name 

    for station1, station2 in connections:
        n1 = _norm_conn_name(station1)
        n2 = _norm_conn_name(station2)
        
        #Check if both normalized station names exist in the graph, important to debug
        if n1 in graph and n2 in graph:
            lat1, lon1 = graph.nodes[n1]['lat'], graph.nodes[n1]['lon']
            lat2, lon2 = graph.nodes[n2]['lat'], graph.nodes[n2]['lon']
            
            #distance between stations, 1.0 by default
            distance = haversine_distance(lat1, lon1, lat2, lon2)
            
            graph.add_edge(n1, n2, distance_km=distance)
            added_edges_count += 1
        else:
            #edbug
            print(f"Warning: Station '{station1}' (norm '{n1}') or '{station2}' (norm '{n2}') not found in the graph.")
            
    print(f"\nSuccessfully added {added_edges_count} edges from the connection list.")
    return graph

#Odio la rnfe tio, mireu que he hagut de fer perque la renfe no sap escriure be les estacions
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
G = add_rail_connections(G, r1_connections)
G = add_rail_connections(G, r2_connections)
G = add_rail_connections(G, r2N_connections)
G = add_rail_connections(G, r2S_connections)
G = add_rail_connections(G, r3_connections)
G = add_rail_connections(G, r4_connections)
G = add_rail_connections(G, r7_connections)
G = add_rail_connections(G, r8_connections)

print(f"Number of nodes (stations): {G.number_of_nodes()}")
print(f"Number of edges (connections): {G.number_of_edges()}")

print("\nNodes and example attributes (ID included):")
for i, node in enumerate(list(G.nodes)[:3]):
    print(f"Node: {node}, Attribute: {G.nodes[node]}")

print("\nEdges and their example attributes:")
for i, edge in enumerate(list(G.edges(data=True))[:3]):
    print(f"Edge: {edge[0]} -> {edge[1]}, Attributes: {edge[2]}")


def visualize_rail_graph(graph: nx.Graph, output_filename="rodalies_map.html"):
    """
    using the folium library to create an interactive map of the rail network.
    This map will display stations as markers and connections as lines.
    Args:
        graph (nx.Graph): The network graph with 'lat' and 'lon' attributes.
        output_filename (str): Name of the HTML file to save the map to.
    """
        
    #we are gonna use the maximum latitude and longitude to center the map
    #this way we are preventing stations taht are far away from being cut off
    latitudes = [data['lat'] for _, data in graph.nodes(data=True) 
                 if data['lat'] is not None and not math.isnan(data['lat'])]
    longitudes = [data['lon'] for _, data in graph.nodes(data=True) 
                  if data['lon'] is not None and not math.isnan(data['lon'])]
                  
    if not latitudes or not longitudes:
        print("Error: No valid coordinates found to create a geographic map.")
        return
    #We use the maximum nstad of the average to ensure all points are visible, are not leave
    max_lat = np.max(latitudes)
    max_lon = np.max(longitudes)

    #the nice background never came, is plain gray
    m = folium.Map(location=[max_lat, max_lon], zoom_start=9, tiles="Stamen Terrain")

    
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
        lat_u, lon_u = graph.nodes[u]['lat'], graph.nodes[u]['lon']
        lat_v, lon_v = graph.nodes[v]['lat'], graph.nodes[v]['lon']
        distance = edge_data.get('distance_km', 'N/A')

        if not any(math.isnan(coord) for coord in [lat_u, lson_u, lat_v, lon_v]):
            # Create a line segment between the two stations
            points = [(lat_u, lon_u), (lat_v, lon_v)]
            folium.PolyLine(
                points,
                color='gray',
                weight=1.5,
                opacity=0.8,
                #The tooltip is useful to show information when hovering over the line
                tooltip=f"Tram: {u} - {v} distance: {distance:.2f} km"
            ).add_to(line_group)

    folium.LayerControl().add_to(m)

    m.save(output_filename)
    print(f"\n✅ Interactive map saved to: {output_filename}\nOpen this file in your browser to view the map.")

if __name__ == "__main__":
    visualize_rail_graph(G)