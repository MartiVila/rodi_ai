import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

# 1. Configuración
# Definimos el lugar (puede ser una ciudad o coordenadas)
lugar = "Barcelona, Spain"

# Definimos el filtro: Queremos infraestructura ferroviaria (rail)
# Excluimos tranvía (tram) y metro (subway) si queremos solo RENFE estricto,
# pero a veces en OSM las etiquetas son confusas. Empecemos con 'rail'.
filtro_tren = '["railway"~"rail"]' 

print(f"Descargando red ferroviaria de {lugar}... esto puede tardar unos segundos.")

# 2. Descargar el Grafo
# simplify=True intenta eliminar nodos intermedios que no son cruces (curvas suaves)
G = ox.graph_from_place(lugar, custom_filter=filtro_tren, simplify=True)

print(f"Grafo descargado con {len(G.nodes)} nodos y {len(G.edges)} tramos de vía.")

# 3. Limpieza básica (Opcional pero recomendada)
# Convertimos a grafo no dirigido para simplificar visualización inicial
G_simple = ox.get_undirected(G)

# 4. Visualización rápida con OSMnx
fig, ax = ox.plot_graph(G, node_size=5, edge_color="r", edge_linewidth=2, bgcolor="black", show=False, close=False)

# 5. Añadir Estaciones Manualmente (Ejemplo)
# OSMnx usa IDs numéricos de OSM. Para añadir tus estaciones lógicas,
# puedes buscar el nodo más cercano a las coordenadas reales de la estación.

# Coordenadas aproximadas (Lat, Lon)
coords_sants = (41.379, 2.140)
coords_sagrera = (41.421, 2.190)

# Encontramos el nodo del grafo más cercano a esas coordenadas
nodo_sants = ox.distance.nearest_nodes(G, X=coords_sants[1], Y=coords_sants[0])
nodo_sagrera = ox.distance.nearest_nodes(G, X=coords_sagrera[1], Y=coords_sagrera[0])

print(f"Nodo OSM más cercano a Sants: {nodo_sants}")
print(f"Nodo OSM más cercano a Sagrera: {nodo_sagrera}")

# Dibujamos estos puntos destacados en el mapa
ax.scatter(G.nodes[nodo_sants]['x'], G.nodes[nodo_sants]['y'], c='cyan', s=100, label='Sants', zorder=5)
ax.scatter(G.nodes[nodo_sagrera]['x'], G.nodes[nodo_sagrera]['y'], c='yellow', s=100, label='Sagrera', zorder=5)

plt.legend()
plt.show()

# 6. ¿Cómo usar esto en tu simulador?
# Ahora G es un objeto NetworkX. Puedes iterar sobre él:
# for u, v, data in G.edges(data=True):
#     longitud = data.get('length', 100) # Longitud en metros real