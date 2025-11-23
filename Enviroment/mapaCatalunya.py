import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import box
import contextily as cx

# 1. Bounding box de Catalunya (aprox) en lon/lat (EPSG:4326)
W, S, E, N = 0.0, 40.5, 3.5, 42.9

bbox_poly = box(W, S, E, N)
gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bbox_poly], crs="EPSG:4326")

# 2. Pasar a Web Mercator
gdf_3857 = gdf.to_crs(epsg=3857)

fig, ax = plt.subplots(figsize=(8, 8))

# Dibujamos el bbox para fijar el extent
gdf_3857.boundary.plot(ax=ax)

# 3. Mapa base de OpenStreetMap (para ver el territorio)
cx.add_basemap(
    ax,
    source=cx.providers.OpenStreetMap.Mapnik,
    crs=gdf_3857.crs.to_string(),
    zoom=8,          # para Catalunya, 7–9 suele ser razonable
)

# 4. Capa ferroviaria de OpenRailwayMap encima
orm_source = "https://a.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"

cx.add_basemap(
    ax,
    source=orm_source,
    crs=gdf_3857.crs.to_string(),
    zoom=8,          # mismo zoom que el base, o muy parecido
)

# 5. Ajustar a Catalunya
ax.set_xlim(gdf_3857.total_bounds[0], gdf_3857.total_bounds[2])
ax.set_ylim(gdf_3857.total_bounds[1], gdf_3857.total_bounds[3])

ax.set_axis_off()
plt.tight_layout()
plt.show()
