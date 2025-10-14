import pandas as panda
import networkx as nx
import math

# Carrega la informació de les estacions des del fitxer CSV
file_path = 'data/estaciones_coordenadas.csv'
try:
    # lectura amb punt i coma (';') com a separador
    data = panda.read_csv(file_path, sep=';')
except Exception:
    # Si falla, intentar llegir amb una coma (',').
    data = panda.read_csv(file_path, sep=',')

#Look for other characters that may generate issues
data.columns = [col.upper().strip().replace(' ', '_').replace('Ó', 'O') for col in data.columns]
#Have the coordinates in it numeric format
data['LATITUD'] = panda.to_numeric(data['LATITUD'], errors='coerce')
data['LONGITUD'] = panda.to_numeric(data['LONGITUD'], errors='coerce')
data.dropna(subset=['LATITUD', 'LONGITUD'], inplace=True)

# Haversine per calcular la distància entre dues coordenades geogràfiques (NO SE COM PODEM TROBAR LA DISTANCIA REAL DE LES VIES)
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Radi de la Terra en km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Crear el graf
G = nx.Graph()

# Afegir estacions com a nodes amb latitud i longitud com a atributs
for index, row in data.iterrows():
    station_name = row['NOMBRE_ESTACION']
    lat = row['LATITUD']
    lon = row['LONGITUD']
    G.add_node(station_name, lat=lat, lon=lon)

# Hauriem de buscar de poder obtenir les connexions reals d'un csv??
# Per ara, afegim algunes connexions d'exemple
example_connections = [
    ('BARCELONA-SANT ANDREU COMTAL', 'BARCELONA-CLOT-ARAGO'),
    ('BARCELONA-CLOT-ARAGO', 'BARCELONA-ESTACIO DE FRANÇA'),
    ('BARCELONA-PASSEIG DE GRACIA', 'BARCELONA-SANTS'),
    ('BARCELONA-SANTS', 'BELLVITGE'),
    ('AEROPORT', 'EL PRAT DE LLOBREGAT')
]

# Afegir arestes al graf i calcular la distància com a atribut de l'aresta
for station1, station2 in example_connections:
    if station1 in G and station2 in G:
        lat1, lon1 = G.nodes[station1]['lat'], G.nodes[station1]['lon']
        lat2, lon2 = G.nodes[station2]['lat'], G.nodes[station2]['lon']
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        G.add_edge(station1, station2, distance_km=distance)

# Pito per saber si afegint bé
print(f"Number of nodes (stations): {G.number_of_nodes()}")
print(f"Number of edges (connections): {G.number_of_edges()}")

print("\nNodes i atributs d'exemple:")
for i, node in enumerate(list(G.nodes)[:3]):
    print(f"Node: {node}, Atribut: {G.nodes[node]}")

print("\nArestes i els seus atributs d'exemple:")
for i, edge in enumerate(list(G.edges(data=True))[:3]):
    print(f"Edge: {edge[0]} -> {edge[1]}, Atributs: {edge[2]}")