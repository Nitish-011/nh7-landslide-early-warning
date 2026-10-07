import json
import math
import numpy as np
import pandas as pd
from pathlib import Path

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

with open('geojson/nh7_route.geojson', 'r', encoding='utf-8') as f:
    gj = json.load(f)
coords = [(c[1], c[0]) for c in gj['features'][0]['geometry']['coordinates']]

dists = [0.0]
for i in range(len(coords) - 1):
    dists.append(dists[-1] + haversine_m(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1]))
total_dist = dists[-1]

step_m = 50.0
target_dists = np.arange(0.0, total_dist, step_m)
if target_dists[-1] < total_dist:
    target_dists = np.append(target_dists, total_dist)

resampled = []
curr_idx = 0
for td in target_dists:
    while curr_idx < len(dists) - 1 and dists[curr_idx + 1] < td:
        curr_idx += 1
    if curr_idx >= len(dists) - 1:
        resampled.append(coords[-1])
        continue
    seg_d = dists[curr_idx + 1] - dists[curr_idx]
    frac = 0.0 if seg_d == 0 else (td - dists[curr_idx]) / seg_d
    lat = coords[curr_idx][0] + frac * (coords[curr_idx + 1][0] - coords[curr_idx][0])
    lon = coords[curr_idx][1] + frac * (coords[curr_idx + 1][1] - coords[curr_idx][1])
    resampled.append([round(lat, 5), round(lon, 5)])

res_chainage = [0.0]
for i in range(len(resampled) - 1):
    res_chainage.append(res_chainage[-1] + haversine_m(resampled[i][0], resampled[i][1], resampled[i+1][0], resampled[i+1][1]) / 1000.0)

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
snapped_indices = [0]
for name, lat, lng in boundaries[1:-1]:
    dists = [haversine_m(lat, lng, r[0], r[1]) for r in resampled]
    snapped_indices.append(int(np.argmin(dists)))
snapped_indices.append(len(resampled) - 1)

seg_names = [
    ('seg_01', 'Rishikesh to Shivpuri'),
    ('seg_02', 'Shivpuri to Byasi'),
    ('seg_03', 'Byasi to Kaudiyala'),
    ('seg_04', 'Kaudiyala to Devprayag'),
    ('seg_05', 'Devprayag to Teen Dhara'),
    ('seg_06', 'Teen Dhara to Kirtinagar'),
    ('seg_07', 'Kirtinagar to Srinagar'),
    ('seg_08', 'Srinagar to Sirobagarh'),
    ('seg_09', 'Sirobagarh to Rudraprayag'),
    ('seg_10', 'Rudraprayag to Gauchar'),
    ('seg_11', 'Gauchar to Karnaprayag'),
    ('seg_12', 'Karnaprayag to Langasu'),
    ('seg_13', 'Langasu to Nandprayag'),
    ('seg_14', 'Nandprayag to Chamoli'),
    ('seg_15', 'Chamoli to Birahi'),
    ('seg_16', 'Birahi to Pipalkoti'),
    ('seg_17', 'Pipalkoti to Helang (Tangani)'),
    ('seg_18', 'Helang to Joshimath')
]

seg_info = []
for i, (sid, sname) in enumerate(seg_names):
    s_idx, e_idx = snapped_indices[i], snapped_indices[i+1]
    s_km, e_km = res_chainage[s_idx], res_chainage[e_idx]
    length_km = e_km - s_km
    seg_info.append({
        'id': sid, 'name': sname, 's_idx': s_idx, 'e_idx': e_idx,
        'start_km': s_km, 'end_km': e_km, 'length_km': length_km
    })# Project 309 scars
df_scars = pd.read_csv('model/nh7_published_309_inventory.csv')
scar_alongs = []
for _, row in df_scars.iterrows():
    slat, slon = row['latitude'], row['longitude']
    cos_lat = math.cos(math.radians(slat))
    min_d = float('inf')
    best_along = 0.0
    for i in range(len(resampled) - 1):
        p1, p2 = resampled[i], resampled[i+1]
        if not (min(p1[0], p2[0]) - 0.03 <= slat <= max(p1[0], p2[0]) + 0.03 and min(p1[1], p2[1]) - 0.03 <= slon <= max(p1[1], p2[1]) + 0.03):
            continue
        R = 6371000.0; rad = math.pi / 180.0
        vx = (p2[1] - p1[1]) * rad * R * cos_lat
        vy = (p2[0] - p1[0]) * rad * R
        wx = (slon - p1[1]) * rad * R * cos_lat
        wy = (slat - p1[0]) * rad * R
        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq == 0: t = 0.0
        else: t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len_sq))
        proj_x, proj_y = t * vx, t * vy
        d = math.hypot(wx - proj_x, wy - proj_y)
        if d < min_d:
            min_d = d
            best_along = res_chainage[i] + t * (res_chainage[i+1] - res_chainage[i])
    scar_alongs.append(best_along)

df_scars['along_km'] = scar_alongs

print(f"Total scars: {len(df_scars)}")
print(f"{'ID':<8} {'Name':<32} {'Start':<7} {'End':<7} {'Len_km':<8} {'Scars':<6} {'Slides_per_km':<12}")
print('-' * 84)
for seg in seg_info:
    s_km, e_km = seg['start_km'], seg['end_km']
    if seg['id'] == 'seg_18':
        m = (df_scars['along_km'] >= s_km) & (df_scars['along_km'] <= e_km + 1.0)
    else:
        m = (df_scars['along_km'] >= s_km) & (df_scars['along_km'] < e_km)
    count = int(m.sum())
    rate = count / seg['length_km'] if seg['length_km'] > 0 else 0
    seg['scars'] = count
    seg['rate'] = rate
    print(f"{seg['id']:8} {seg['name']:32} {s_km:6.2f} {e_km:6.2f} {seg['length_km']:7.2f} {count:<6} {rate:<12.2f}")

print(f"Total scars assigned: {sum(s['scars'] for s in seg_info)}")
