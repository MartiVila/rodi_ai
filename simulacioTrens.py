import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
from shapely.geometry import LineString
import time

# ===============================
# 1️⃣ Crear línea R1 a partir de estaciones conocidas
# Coordenadas aproximadas de las estaciones de Barcelona a Maçanet
# Formato: (longitud, latitud) en EPSG:4326
estaciones_R1 = [
    (2.140, 41.378),  # Barcelona Sants
    (2.163, 41.384),  # Passeig de Gràcia
    (2.180, 41.386),  # Arc de Triomf
    (2.200, 41.390),  # Clot
    (2.228, 41.400),  # Sant Andreu Arenal
    (2.260, 41.417),  # Montcada i Reixac
    (2.290, 41.435),  # Mataró
    (2.350, 41.450),  # Calella
    (2.400, 41.465),  # Arenys de Mar
    (2.450, 41.480),  # Maçanet-Massanes
]

# Crear LineString
linea_R1 = LineString(estaciones_R1)

# Convertir a GeoDataFrame y reproyectar
gdf_linea = gpd.GeoDataFrame(geometry=[linea_R1], crs="EPSG:4326")
gdf_linea = gdf_linea.to_crs(epsg=3857)

linea_geom = gdf_linea.geometry.iloc[0]

# ===============================
# 2️⃣ Configurar figura centrada en la línea
# ===============================
fig, ax = plt.subplots(figsize=(12, 12))
minx, miny, maxx, maxy = linea_geom.bounds
margin = 1000
ax.set_xlim(minx - margin, maxx + margin)
ax.set_ylim(miny - margin, maxy + margin)

# Mapa base
cx.add_basemap(ax,
            source=cx.providers.OpenStreetMap.Mapnik,
            crs=gdf_linea.crs.to_string(),
            zoom=13)

# Dibujar línea R1
x, y = linea_geom.xy
ax.plot(x, y, linewidth=4, color="tab:blue", alpha=0.8, label="R1")
ax.legend(loc="upper right", fontsize=10)
ax.set_axis_off()

# ===============================
# 3️⃣ Animar trenes sobre la línea
# ===============================
trenes = [
    {"pos": 0.0, "vel": 0.002, "color": "red"},
    {"pos": 0.5, "vel": 0.003, "color": "green"},
]

markers = []
for tren in trenes:
    pos_geom = linea_geom.interpolate(tren["pos"], normalized=True)
    marker, = ax.plot([pos_geom.x], [pos_geom.y], "o", color=tren["color"], markersize=8)
    markers.append(marker)

plt.show(block=False)

for _ in range(1000):
    for tren, marker in zip(trenes, markers):
        tren["pos"] += tren["vel"]
        if tren["pos"] > 1.0:
            tren["pos"] = 0.0
        pos_geom = linea_geom.interpolate(tren["pos"], normalized=True)
        marker.set_data([pos_geom.x], [pos_geom.y])
    fig.canvas.draw()
    fig.canvas.flush_events()
    time.sleep(0.05)
