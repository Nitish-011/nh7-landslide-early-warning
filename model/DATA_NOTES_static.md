# Dataset notes: NH-7 static susceptibility model

## Source and citation
Positives: Mey, J., Guntu, R. K., Plakias, A., Silva de Almeida, I., and Schwanghart, W. (2024). More than one landslide per road kilometer - surveying and modelling mass movements along the Rishikesh-Joshimath (NH-7) highway, Uttarakhand, India. Nat. Hazards Earth Syst. Sci., 24, 3207. https://doi.org/10.5194/nhess-24-3207-2024
Check the supplement's license/terms before redistributing the data, and cite it in the pitch and the paper.

## What this dataset is
- 309 positives (surveyed road-blocking landslides) and 927 negatives
  (ratio 3.0 : 1, at least 250 m from any positive).
- Mode A: Negatives lie on the real road (OpenStreetMap geometry), with sideways offsets copied from the positives' own distance distribution.
- Road source: cache nh7_road_osm_cache.json
- Features (terrain only): elevation_m, slope_deg, aspect_sin, aspect_cos, local_relief_m. No rainfall: apply it at serving time.

## Checks run
Leak test (distance-to-route alone must predict nothing; pass if |AUC-0.5| <= 0.07):
- dist_ref_km: AUC 0.486 (95% CI 0.450-0.523)
Result: PASS
Terrain failures: 0. Elevation vs the inventory's own DEM: median |diff| 31 m, r=0.992 (OK)

## Spatial-block CV (6 blocks along the road, 2.0 km buffer)
| experiment | pooled AUC | block AUC mean +- sd | AP | top-20% capture |
|---|---|---|---|---|
| slope only (LR) | 0.703 | 0.676 +- 0.041 | 0.422 | 38% |
| elevation only (LR) | 0.545 | 0.406 +- 0.037 | 0.253 | 15% |
| terrain (LR) | 0.729 | 0.620 +- 0.060 | 0.460 | 43% |
| terrain (RF) | 0.708 | 0.602 +- 0.079 | 0.450 | 39% |
How to read it: pooled AUC ranks points across the whole corridor; block AUC ranks points
within each stretch. Elevation can look strong per block but weak pooled because it rises
steadily towards Joshimath.
Chance: AUC 0.5, top-20% capture 20%. Best model: terrain (LR) -> moderate
(heuristic labels: <0.58 none, <0.70 weak, otherwise moderate).

## Limitations
- Positives are road-blocking landslides, mostly from one rainfall episode (Sept-Oct 2022); points, not polygons.
- Negatives are background points, not confirmed stable ground.
- Terrain from a 90 m DEM with a 150 m finite-difference stencil: coarse for road-cut slopes.
- No lithology or road-widening feature, which Mey et al. identify as main controls.
- No rainfall feature: apply live rainfall at serving time as an explicit, explainable factor.
