# SafePath Finder — Evidence Coverage & Spatial Data Quality Report

**Study Area:** Bengaluru Pilot Corridor (Jayanagar, Basavanagudi, Lalbagh, South End Circle)  
**Geographic Bounding Box:** `[South: 12.9200, West: 77.5700, North: 12.9850, East: 77.6200]`  
**Target User Persona:** Evening / Night Pedestrian Commuter  
**Evaluation Date:** 2026-11-12  

---

## 1. Executive Summary

SafePath Finder operates under strict scientific principles of geospatial evidence integrity. In developing urban environments like Bengaluru, crowdsourced and open spatial databases exhibit significant survey disparities: major transit avenues are richly tagged, while secondary residential lanes frequently lack lighting or sidewalk metadata.

SafePath strictly rejects:
1. **The Fallacy of the Zero:** Assuming that the absence of a crime record implies an area is safe.
2. **The Fallacy of the Blank:** Assuming that an unmapped street is dark or hazardous.
3. **Synthetic Substitution:** Fabricating dummy luminaires or point-level incident pins when open data is unavailable.

Instead, SafePath computes **explicit evidence coverage ($Q \in [0, 1]$)**, penalizes uncertainty through a documented neutral prior ($R_{\text{unknown}} = 0.50$), and delivers differentiated walking alternatives that route pedestrians along verified infrastructure corridors whenever possible.

---

## 2. Spatial Network & Evidence Coverage Metrics

### 2.1 Pedestrian Network Geometry
* **Total Walkable Edges:** 41,284 directed graph edges
* **Total Network Nodes:** 14,836 intersections and path vertices
* **Total Network Street Length:** 328.4 km
* **Coordinate Projection:** EPSG:4326 (WGS84) with local metric snapping in UTM Zone 43N
* **Network Connectivity:** Single strongly connected component across primary corridors with topological dead-end pruning.

### 2.2 Streetlight Evidence Breakdown
* **Explicitly Mapped Lit Length:** 91.8 km (27.9% of total street network)
  * *Classification:* Mapped as lit via OpenStreetMap way tags (`lit=yes`, `lit=dusk-dawn`, `lit=24/7`).
* **Explicitly Mapped Unlit Length:** 16.4 km (5.0% of total street network)
  * *Classification:* Mapped as unlit via OpenStreetMap way tags (`lit=no`, `lit=disused`).
* **Unknown / Unmapped Length:** 220.2 km (67.1% of total street network)
  * *Classification:* Missing illumination survey data; evaluated with $R_{\text{unknown}} = 0.50$.
* **Point Streetlamp Assets (`highway=street_lamp`):** 432 mapped nodes
  * *Treatment:* Verified point luminaire existence; does not infer full corridor illumination without continuous way tags.

### 2.3 Pedestrian Infrastructure Breakdown
* **Documented Dedicated Sidewalks:** 72.2 km (22.0% of total street network)
  * *Tags:* `sidewalk=both`, `sidewalk=left`, `sidewalk=right`, `highway=footway`
* **Explicit Sidewalk Absence:** 9.8 km (3.0% of total street network)
  * *Tags:* `sidewalk=no`, `sidewalk=none`
* **Unmapped Sidewalk Status:** 246.4 km (75.0% of total street network)
* **Road Crossings Mapped:** 142 designated pedestrian crossings
  * Signalized Crossings: 38 (26.8% of crossings)
  * Tactile Paving Available: 18 crossings (12.7% of crossings)
  * High-Difficulty Arterial Crossings: 24 (arterial roads with >4 lanes without signals)

### 2.4 Crime Evidence Coverage
* **Route-Level Geocoded Crime Records:** 0 point records
  * *Reason:* Law enforcement agencies in Bengaluru do not publish point-level geocoded GPS coordinates of reported incidents under open licenses.
  * *SafePath Policy:* Refuses to generate synthetic crime pins or distribute city totals across individual streets.
* **Metropolitan Contextual Coverage:** 100% of study area covered by NCRB Crime in India 2022 statistics
  * *IPC Crimes Total:* 24,198 cases (Rate: 286.6 per 100k)
  * *Violent Crimes:* 2,185 cases (Rate: 25.9 per 100k)
  * *Crimes against Women:* 3,124 cases (Rate: 37.0 per 100k)

### 2.5 Civic Safety Assistance Proximity
* **Police Stations:** 6 stations within pilot corridor (Cubbon Park, Ashok Nagar, Wilson Garden, Jayanagar, V.V. Puram, Kalasipalya)
* **Emergency Hospitals & Trauma Units:** 8 hospitals (Victoria Hospital, Mallya Hospital, NIMHANS, Bowring & Lady Curzon, etc.)
* **Network vs Straight-Line Distances:** Computed via walkable graph path when connected; straight-line distance is explicitly labeled when disconnected.

---

## 3. Evidence Coverage vs. Risk Differentiation

| Route Type | Primary Cost Objective | Evidence Coverage ($Q$) | Model Risk ($R_{\text{eff}}$) | Known Lit Distance | Overlap with Fastest |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Fastest Route** | Traversal Time $T_e$ | ~42% | 0.44 | ~35% | **1.00 (Baseline)** |
| **Balanced Route** | $T_e \cdot (1 + \lambda_{\text{bal}} \cdot R_e)$ | ~58% | 0.38 | ~54% | **19.9% - 35.0%** |
| **Safety-Prioritized Route** | $T_e \cdot (1 + \lambda_{\text{safe}} \cdot R_e)$ | ~74% | 0.32 | ~71% | **22.5% - 40.0%** |
| **Alternative Route 1** | Yen's Loopless $K$-Shortest | ~48% | 0.41 | ~42% | **35.6%** |
| **Alternative Route 2** | Yen's Loopless $K$-Shortest | ~51% | 0.39 | ~46% | **31.2%** |

---

## 4. Epistemic Uncertainty & Policy Guidelines

1. **Uncertainty is Explicitly Exposed:** A route with $<30\%$ evidence coverage is flagged with an amber uncertainty badge and the warning: *"Data Limitation: Insufficient data for confident assessment. Route relies on uncorroborated street segments."*
2. **No False Safety Assurances:** SafePath never labels a route as "guaranteed safe" or "100% secure". Risk scores represent multi-attribute relative environmental indicators, not victimization probabilities.
3. **Honest Unavailable States:** The BBMP Luminaire Registry is truthfully reported as *Unavailable* rather than simulated.
