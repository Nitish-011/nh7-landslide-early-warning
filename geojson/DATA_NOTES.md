# Dataset Notes: NH-7 Landslide Risk Classifier

## Strategy used in this run
**STATIC (terrain-only) model.** Only 0 NASA GLC points had usable dates (below the 10-event threshold), so this run falls back to 28 NGDR points as positives, with no rainfall features at all.

## Source tracking
Every row has a `source` column: `nasa_glc`, `ngdr_static`, or `interpolated_negative`.

## Limitations
- This model does NOT react to live rainfall — it scores terrain susceptibility only.
- If the hackathon demo needs to show risk responding to live weather, don't fake this in the model: apply a simple, explainable rainfall multiplier on top of this static score in the backend at serving time instead, and say so plainly if asked.
- Confirm separately whether the NGDR source used here is a true dated-event inventory or a geomorphology/terrain-classification layer — that distinction isn't resolved by this script and affects how the `ngdr_static` points should be described.

## Features
- `elevation_m`, `slope_deg`, `aspect_deg`: computed via finite differences using 4 points
  offset 150m from center (Open-Meteo GLO-90 elevation API).
- `nearest_segment_id`: nearest-neighbor match to the 18 NH-7 segments, for spatial
  (not random) train/test splitting.


## Counts from this run
- NASA GLC raw yield in bounding box: 0
- NASA GLC usable (dated) events: 0
- NGDR points available: 28
- Negative points generated: 150
- Final rows after dropping missing data: 96 (dropped 82)
- Class balance: {0: 78, 1: 18}
