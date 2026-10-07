import json
import math
import sys
import numpy as np

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


with open('geojson/nh7_route.geojson', 'r', encoding='utf-8') as f:
    gj = json.load(f)
coords = [(c[1], c[0]) for c in gj['features'][0]['geometry']['coordinates']]

chainage = [0.0]
for i in range(len(coords) - 1):
    d = haversine_m(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1]) / 1000.0
    chainage.append(chainage[-1] + d)

total_len = chainage[-1]
print(f'Total chainage: {total_len:.2f} km')

boundaries = [
    ('Rishikesh', 30.0869, 78.2676),
    ('Shivpuri', 30.1357, 78.3892),
    ('Byasi', 30.1472, 78.4839),
    ('Kaudiyala', 30.0765, 78.5028),
    ('Devprayag', 30.1459, 78.5986),
    ('Teen Dhara', 30.2015, 78.6820),
    ('Kirtinagar', 30.2173, 78.7456),
    ('Srinagar', 30.2224, 78.7845),
    ('Sirobagarh', 30.2390, 78.8540),
    ('Rudraprayag', 30.2844, 78.9811),
    ('Gauchar', 30.2872, 79.1557),
    ('Karnaprayag', 30.2587, 79.2173),
    ('Langasu', 30.2980, 79.2550),
    ('Nandprayag', 30.3308, 79.3242),
    ('Chamoli', 30.4074, 79.3524),
    ('Birahi', 30.4350, 79.3900),
    ('Pipalkoti', 30.4297, 79.4304),
    ('Helang', 30.5280, 79.5380),
    ('Joshimath', 30.5564, 79.5663),
]

snapped_indices = []
print(f'{"Town":<15} {"Orig Lat,Lng":<22} {"Snap Lat,Lng":<22} {"Dist(m)":<10} {"Chainage(km)":<12}')
print('-' * 85)
for name, lat, lng in boundaries:
    dists = [haversine_m(lat, lng, c[0], c[1]) for c in coords]
    idx = int(np.argmin(dists))
    snapped_indices.append(idx)
    min_d = dists[idx]
    c_lat, c_lng = coords[idx]
    ch = chainage[idx]
    print(f'{name:<15} ({lat:.4f}, {lng:.4f})     ({c_lat:.4f}, {c_lng:.4f})     {min_d:<10.1f} {ch:<12.2f}')

print('\nCheck monotonicity of snapped indices:')
print('Snapped indices:', snapped_indices)
is_sorted = all(snapped_indices[i] <= snapped_indices[i+1] for i in range(len(snapped_indices)-1))
print('Monotonically increasing:', is_sorted)
