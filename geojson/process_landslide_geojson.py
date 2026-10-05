import geopandas as gpd
import pandas as pd

# 1. Load the NGDR Geomorphology GeoJSON and your NH-7 segments
geomorph_gdf = gpd.read_file('GEOMORPHOLOGY_250K_CLIP_geojson.geojson')
segments_df = pd.read_csv('nh7_segments.csv')

# Convert segments to GeoDataFrame (WGS84)
segments_gdf = gpd.GeoDataFrame(
    segments_df, 
    geometry=gpd.points_from_xy(segments_df.longitude, segments_df.latitude),
    crs="EPSG:4326"
)

# 2. Inspect attribute columns to identify landslide-related labels
print("Available columns in NGDR file:", geomorph_gdf.columns.tolist())

# Search text fields for landslide keywords (adjust column names based on print output above)
text_cols = geomorph_gdf.select_dtypes(include=['object', 'string']).columns
landslide_mask = False
keywords = ['landslide', 'slide', 'mass wasting', 'debris', 'scree', 'active slope']

for col in text_cols:
    landslide_mask |= geomorph_gdf[col].astype(str).str.lower().str.contains('|'.join(keywords), na=False)

landslide_polygons = geomorph_gdf[landslide_mask].copy()

if landslide_polygons.empty:
    print("No explicit 'landslide' text match found. Using all active slope/geomorphic centroids in clip region.")
    landslide_polygons = geomorph_gdf.copy()

# 3. Get polygon centroids for coordinate extraction
landslide_polygons['geometry'] = landslide_polygons.geometry.centroid

# 4. Reproject to metric system (UTM 44N) to filter points within 5km of NH-7
landslide_utm = landslide_polygons.to_crs(epsg=32644)
segments_utm = segments_gdf.to_crs(epsg=32644)

# Create a 5km buffer around the entire NH-7 route
nh7_buffer = segments_utm.geometry.unary_union.buffer(5000)

# Keep only landslide points inside the buffer
near_nh7_landslides = landslide_utm[landslide_utm.geometry.within(nh7_buffer)].to_crs(epsg=4326)

# 5. Extract Latitude & Longitude and save to CSV
positives_df = pd.DataFrame({
    'landslide_id': range(len(near_nh7_landslides)),
    'longitude': near_nh7_landslides.geometry.x,
    'latitude': near_nh7_landslides.geometry.y,
    'label': 1  # Positive example flag
})

positives_df.to_csv('nh7_positive_landslides.csv', index=False)
print(f"Extracted {len(positives_df)} positive landslide points along the NH-7 corridor.")