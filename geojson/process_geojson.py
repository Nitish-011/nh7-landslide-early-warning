import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
import numpy as np

# 1. Load the GeoJSON you just downloaded
# Replace with your actual file path
gdf = gpd.read_file('nh7_route.geojson')

# 2. Project to a metric Coordinate Reference System (UTM Zone 44N for Uttarakhand)
# This allows us to measure distances in meters rather than degrees
gdf_projected = gdf.to_crs(epsg=32644)

# 3. Extract the LineString geometry
highway_line = gdf_projected.geometry.iloc[0]

# 4. Generate points every 3km (3000 meters)
segment_length = 3000
distances = np.arange(0, highway_line.length, segment_length)
points = [highway_line.interpolate(distance) for distance in distances]

# 5. Convert points back to a GeoDataFrame and reproject to standard Lat/Lon (WGS84)
points_gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:32644")
points_gdf = points_gdf.to_crs(epsg=4326)

# 6. Extract Latitude and Longitude into standard columns and save to CSV
points_gdf['longitude'] = points_gdf.geometry.x
points_gdf['latitude'] = points_gdf.geometry.y
points_gdf.drop(columns='geometry').to_csv('nh7_segments.csv', index_label='segment_id')

print(f"Successfully generated {len(points_gdf)} highway segments.")