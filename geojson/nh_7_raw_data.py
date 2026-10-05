import pandas as pd
import requests
import time

# 1. Load your positive points and your road segments
positives = pd.read_csv('nh7_positive_landslides.csv')[['longitude', 'latitude', 'label']]
segments = pd.read_csv('nh7_segments.csv')

# 2. Create negative examples (label = 0) by sampling 30 random points
negatives = segments.sample(n=30, random_state=42).copy()
negatives['label'] = 0
negatives = negatives[['longitude', 'latitude', 'label']]

# 3. Assemble the Master Training Table
train_df = pd.concat([positives, negatives], ignore_index=True)

# 4. Batch Fetch Terrain Data (Elevation)
print("Fetching elevation data in a single batch...")

# Convert columns to comma-separated strings
lat_str = ",".join(train_df['latitude'].astype(str))
lon_str = ",".join(train_df['longitude'].astype(str))

url = f"https://api.open-meteo.com/v1/elevation?latitude={lat_str}&longitude={lon_str}"

max_retries = 3
for attempt in range(max_retries):
    try:
        # Added a 15-second timeout so it doesn't hang indefinitely
        response = requests.get(url, timeout=15).json()
        
        if 'elevation' in response:
            train_df['elevation_m'] = response['elevation']
            print("Successfully fetched all elevations!")
            break
        else:
            print(f"API Error Response: {response}")
            break
            
    except Exception as e:
        print(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(2) # Wait 2 seconds before retrying

# Save the final table
train_df.to_csv('nh7_training_data_raw.csv', index=False)
print(f"Created training table with {len(train_df)} rows.")
print(train_df.head())