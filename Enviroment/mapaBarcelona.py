import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import box
import contextily as cx

# 1. Bounding box de Barcelona (aprox) en WGS84
W, S, E, N = 2.05, 41.30, 2.25, 41.47

bbox_poly = box(W, S, E, N)
gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bbox_poly], crs="EPSG:4326")

# 2. Pasar a Web Mercator
gdf_3857 = gdf.to_crs(epsg=3857)

fig, ax = plt.subplots(figsize=(8, 8))

# (Opcional) dibujar el bbox solo para forzar el extent
gdf_3857.boundary.plot(ax=ax)

# 3. Mapa base de Barcelona (OpenStreetMap)
cx.add_basemap(
    ax,
    source=cx.providers.OpenStreetMap.Mapnik,
    crs=gdf_3857.crs.to_string(),
    zoom=13,
)

# 4. Capa ferroviaria de OpenRailwayMap ENCIMA
orm_source = "https://a.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"

cx.add_basemap(
    ax,
    source=orm_source,
    crs=gdf_3857.crs.to_string(),
    zoom=13,
    # zoom_adjust=0  # puedes tocar esto si se ve raro
)

# 5. Ajustar a Barcelona
ax.set_xlim(gdf_3857.total_bounds[0], gdf_3857.total_bounds[2])
ax.set_ylim(gdf_3857.total_bounds[1], gdf_3857.total_bounds[3])

ax.set_axis_off()
plt.tight_layout()
plt.show()
