from scraper_oneuse import scrape_rodalies_line_stations
import pandas as panda
import networkx as nx
import math
import matplotlib.pyplot as plt

# Stations data file path
file_path = 'data/estaciones_coordenadas.csv' 
    # Make the code able to read both ; and , as separators
data = panda.read_csv(file_path, sep=';',engine='python',encoding='latin1')

# Look for other characters that may generate issues and uppercase column names
data.columns = [col.upper().strip().replace('Ó', 'O') for col in data.columns]

# Convert coordinates to numeric format
data['LATITUD'] = panda.to_numeric(data['LATITUD'], errors='coerce')
data['LONGITUD'] = panda.to_numeric(data['LONGITUD'], errors='coerce')
data.dropna(subset=['LATITUD', 'LONGITUD'], inplace=True)

# --- 2. Haversine Distance Function ---

# We use the haversine formula to calculate distances between stations based on coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the great-circle distance between two points on the Earth (Haversine formula)."""
    R = 6371  # Earth's radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


print("Data shape:", data.shape)
print(data.head())

# Graph creation
G = nx.Graph()

# Add stations as nodes with ID, latitude, and longitude as attributes
print(data.iterrows())

for index, row in data.iterrows():
    # Assuming the column for the ID is now named 'ID' after column cleaning

    print(f"Processing row {index}: {row.to_dict()}")

    station_id = row.get('ID') 
    station_name = row.get('NOMBRE_ESTACION')
    lat = row.get('LATITUD')
    lon = row.get('LONGITUD')
    # Add the ID to the node attributes
    G.add_node(station_name, id=station_id, lat=lat, lon=lon) 
    print(f"Added station: {station_name} with ID: {station_id}, Lat: {lat}, Lon: {lon}")

def add_rail_connections(graph: nx.Graph, connections: list):
    """
    Adds edges (connections) to a NetworkX graph, calculating the distance 
    between connected stations using the haversine formula.
    """
    added_edges_count = 0
    for station1, station2 in connections:
        # Check if both stations exist in the graph
        if station1 in graph and station2 in graph:
            # Get coordinates from node attributes
            lat1, lon1 = graph.nodes[station1]['lat'], graph.nodes[station1]['lon']
            lat2, lon2 = graph.nodes[station2]['lat'], graph.nodes[station2]['lon']
            
            # Calculate the distance
            distance = haversine_distance(lat1, lon1, lat2, lon2)
            
            # Add the edge with the calculated distance as an attribute
            graph.add_edge(station1, station2, distance_km=distance)
            added_edges_count += 1
        else:
            print(f"Warning: Station '{station1}' or '{station2}' not found in the graph.")
            
    print(f"\nSuccessfully added {added_edges_count} edges from the connection list.")
    return graph

# Example connections (use your real data here if available)
r1_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r1-molins-de-rei-macanet-massanes-by-mataro")
#r2_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r2-barcelona-sants-maçanet-massanes-by-blanes")
#r2N_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r2n-barcelona-sants-maçanet-massanes-by-blanes-north")
#r3_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r3-barcelona-sants-laroca-del-valles-by-vic")
#r4_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r4-barcelona-sants-sant-just-desvern-by-sant-boi")
#r7_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r7-barcelona-puigcerda-by-granollers-centre")
#r8_connections = scrape_rodalies_line_stations("https://cercanias.info/en/rodalies-catalunya/lines/r8-barcelona-sant-andreu-aeroport-by-cerdanyola-uvic")


# Use the function to add edges and calculate distances
G = add_rail_connections(G, r1_connections)
#G = add_rail_connections(G, r2_connections)
#G = add_rail_connections(G, r2N_connections)
#G = add_rail_connections(G, r3_connections)
#G = add_rail_connections(G, r4_connections)
#G = add_rail_connections(G, r7_connections)
#G = add_rail_connections(G, r8_connections)

# Verification prints
print(f"Number of nodes (stations): {G.number_of_nodes()}")
print(f"Number of edges (connections): {G.number_of_edges()}")

print("\nNodes i atributs d'exemple (ID included):")
for i, node in enumerate(list(G.nodes)[:3]):
    print(f"Node: {node}, Atribut: {G.nodes[node]}")

print("\nArestes i els seus atributs d'exemple:")
for i, edge in enumerate(list(G.edges(data=True))[:3]):
    print(f"Edge: {edge[0]} -> {edge[1]}, Atributs: {edge[2]}")

'''
def visualize_rail_graph(graph: nx.Graph):
    """
    Visualizes the rail network graph using Matplotlib, mapping node positions 
    to their geographic coordinates (latitude and longitude).
    """
    print("\nStarting graph visualization...")
    
    # 1. Prepare node positions using latitude and longitude
    # Matplotlib expects (x, y) coordinates, so we map (longitude, latitude)
    pos = {node: (data['lon'], data['lat']) for node, data in graph.nodes(data=True)}
    
    # 2. Setup the plot
    plt.figure(figsize=(12, 12))
    plt.title("Rail Network Visualization (Example Connections)", fontsize=16)

    # 3. Draw Nodes (Stations)
    nx.draw_networkx_nodes(
        graph, 
        pos, 
        node_size=50,             # Smaller nodes
        node_color='#3b82f6',     # Blue for stations
        alpha=0.8,                
        label='Rail Stations'
    )
    
    # 4. Draw Edges (Rail Connections)
    nx.draw_networkx_edges(
        graph, 
        pos, 
        edge_color='gray',        # Gray lines for tracks
        width=1.5,
        alpha=0.6,
        label='Connections'
    )
    
    # 5. Draw Labels for ONLY the connected stations for clarity
    # We filter for nodes that have at least one connection
    connected_nodes = list(set([n for edge in graph.edges() for n in edge]))
    
    # Create the positions dictionary only for connected nodes
    connected_pos = {n: pos[n] for n in connected_nodes}
    
    # Draw labels
    nx.draw_networkx_labels(
        graph, 
        connected_pos, 
        labels={n: n for n in connected_nodes}, # Use station name as label
        font_size=8,
        font_color='black',
        font_weight='bold'
    )

    # 6. Final Plot Customization
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.axis('on') # Ensure axis is visible for geographical context
    plt.grid(True, alpha=0.3)
    
    # Display the plot
    plt.show()

# --- 5. Run Visualization ---

visualize_rail_graph(G)
'''