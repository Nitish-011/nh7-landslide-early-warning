# Dataset notes v2

Positives: Mey, J., Guntu, R. K., Plakias, A., Silva de Almeida, I., and Schwanghart, W. (2024). More than one landslide per road kilometer - surveying and modelling mass movements along the Rishikesh-Joshimath (NH-7) highway, Uttarakhand, India. Nat. Hazards Earth Syst. Sci., 24, 3207. https://doi.org/10.5194/nhess-24-3207-2024

Chosen feature set: **B  Copernicus 30 m terrain** (8 features) with RF; pooled spatial-block AUC 0.767 (moderate; heuristic labels).

Feature sets compared (pooled AUC, best model per set):
- A  Open-Meteo 90 m terrain: 0.729 (LR)
- B  Copernicus 30 m terrain: 0.767 (RF)
- C  B + rivers/streams: 0.770 (RF)
- D  C + Mey layers: 0.757 (LR)

Caveats: Copernicus DEM is a surface model (trees/buildings included). Streams come from OpenStreetMap and may be incomplete. Lithology/faults/widening only enter if you supplied the Mey layers.
