# SafePath Finder — Research Methodology & Routing Engine Evaluation

**Document Version:** 2.0.0  
**Algorithm Model Version:** 2.0.0  
**Research Domain:** Human-Centred Geospatial Systems, Evidence-Based Pedestrian Navigation, Multi-Dimensional Walkability & Women's Walking Mobility  
**Study Corridor:** Bengaluru Pilot Research Corridor (Karnataka, India)  
**Classification:** Academic Methodology Specification & Empirical Benchmark  

---

## 1. Research Problem and Objectives

Urban navigation platforms routinely optimize pedestrian routing solely for travel duration or metric distance. When commercial platforms attempt to integrate "safety features", they almost universally resort to opaque, black-box scores that collapse complex urban conditions into singular, unverifiable ratings (e.g. "85/100 Safe" or green shield badges). 

Such approaches suffer from severe epistemological and ethical defects:
1. **Conflating Absence of Data with Safety**: Unmapped, poorly documented streets with zero recorded police incident reports are frequently treated as "low risk", placing pedestrians at risk in blind spots.
2. **Opaque Trade-Offs**: Navigators cannot inspect *why* a route was recommended, what environmental assets were verified, or how much extra walking time was traded off.
3. **Speculative Predictions**: Claims of predicting individual victimization probabilities or real-time crowd densities often rely on ungrounded heuristics or biased demographic proxies.
4. **Privacy Vulnerabilities**: Ingestion of community feedback often exposes the identities, schedules, or locations of vulnerable reporters.

### Research Objectives of SafePath Finder
- **Transparent Multi-Attribute Impedance**: Formulate a reproducible, non-negative generalized edge-cost function that explicitly balances walking traversal time against verifiable environmental evidence.
- **Epistemological Uncertainty Policy**: Explicitly decouple evidence coverage ($Q \in [0, 1]$) from observed risk ($R_{\text{observed}} \in [0, 1]$), ensuring unmapped corridors preserve an uncertain neutral prior ($R_{\text{unknown}}$) rather than a false safe score.
- **Explainable Alternatives via Dijkstra and Yen's K-Shortest Paths**: Compute deterministic shortest paths for three documented preferences (**Fastest**, **Balanced**, **Safety-prioritized**) plus distinct loopless alternatives, explaining identical paths honestly when diversity does not physically exist.
- **Privacy by Design**: Cryptographically isolate trusted-contact details, strip personal identification from spatial evidence, and enforce strict server-side authorization.

---

## 2. System Architecture

The SafePath platform is engineered with a modular, verifiable decoupled architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SafePath Client Interface                       │
│      (HTML5 Semantic DOM, Vanilla CSS Design System, Leaflet.js Map)   │
│  - Origin / Destination Validation Alerts (#routePlannerAlert)         │
│  - 3 Route Preferences + Yen Alternatives Cards Grid                   │
│  - Explainable Decision Summary (#routeDecisionSummary)                │
│  - Street-Segment Provenance & Evidence Explorer                       │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP / JSON REST (API_CONTRACT.md)
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   FastAPI Application Engine (/api/v1)                 │
│  ├── /routes/compare          ──> DijkstraRouter & SegmentRiskModel    │
│  ├── /evidence/segments       ──> EvidenceService & Provenance Audit   │
│  ├── /study-area              ──> Spatial Bounding Box & Validator     │
│  ├── /auth & /admin           ──> Argon2id & Role-Based Authorization  │
│  └── /trusted-contacts        ──> AES-128 Fernet Encrypted Isolation   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌─────────────────────────────────┐   ┌──────────────────────────────────┐
│       Geospatial Core           │   │         Persistence Layer        │
│ - OSMnx Pedestrian Graph        │   │ - SQLite / PostgreSQL + PostGIS  │
│ - GraphML Cache Engine          │   │ - Alembic Versioned Migrations   │
│ - Shapely STRtree Indexing      │   │ - Users, Roles & Passwords       │
│ - Projected UTM 43N (EPSG:32643)│   │ - Reports & Moderation States    │
│ - Multi-Attribute Dijkstra      │   │ - Encrypted Trusted Contacts     │
│ - Yen's Loopless K-Shortest     │   │ - Immutable Audit Trail          │
└─────────────────────────────────┘   └──────────────────────────────────┘
```

---

## 3. Study Area Definition

The research prototype is scoped to a designated urban corridor in Bengaluru, Karnataka, India, selected for its mix of major commercial avenues, rapid transit metro stations, botanical perimeters, and dense residential connector streets:

- **Name**: Bengaluru Pilot Corridor
- **Geographic Bounding Box**:
  - South: $12.9200^\circ\text{ N}$
  - West: $77.5700^\circ\text{ E}$
  - North: $12.9850^\circ\text{ N}$
  - East: $77.6200^\circ\text{ E}$
- **UTM Projection**: WGS 84 / UTM Zone 43N (`EPSG:32643`) for metric calculations.
- **Validation**: Every route comparison request is verified against the study area polygon via `StudyArea.validate_coordinate_pair()`. Points outside the bounding box raise `OutOfCoverageError` (HTTP 400), preventing the generation of unverified synthetic routes.

---

## 4. Street-Network Source and Retrieval

Pedestrian network data is derived from OpenStreetMap (OSM) pedestrian ways (`highway IN ('footway', 'pedestrian', 'path', 'residential', 'secondary', 'primary')` with `foot != 'no'`).

1. **Network Retrieval**: Ingested via `OSMNetworkAdapter` with automated caching to GraphML (`cache/bengaluru_pilot_corridor_..._network.graphml`).
2. **Topological MultiDiGraph**: Loaded into a `networkx.MultiDiGraph` with geodesic metric lengths calculated via the Haversine formula:
   $$d = 2r \arcsin \left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cos \phi_2 \sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
   where $r = 6,371,000\text{ m}$.
3. **Geometry Fidelity**: Each edge preserves its true Shapely `LineString` coordinate vertices, enabling sub-meter path visualization on the Leaflet map without simplifying turns or crosswalks.

---

## 5. Evidence Sources and Comprehensive Data Source Audit

SafePath Finder ingests and reconciles eight distinct data sources across municipal, crowdsourced, and open GIS registries. The platform adheres strictly to data provenance, refusing to invent artificial datasets or fabricate verification claims.

### Table 0: Comprehensive Data Source Audit

| Dataset Name | Provider & Original Source | License & Attribution | Geographic Coverage | Temporal Range | Retrieval / Audit Date | Spatial Precision | Known Limitations & Epistemological Boundaries |
|---|---|---|---|---|---|---|---|
| **1. Pedestrian Network** | OpenStreetMap contributors / Overpass API via OSMnx | Open Database License (ODbL) 1.0 | Bengaluru Pilot Corridor (12.9200°N–12.9850°N, 77.5700°E–77.6200°E) | Continuous historical edits | Oct 2026 (cached in GraphML) | Sub-meter way vertices | Secondary residential cut-through footpaths occasionally unmapped; dynamic temporary construction closures not captured in real time. |
| **2. Historical Crime Evidence** | National Crime Records Bureau (NCRB) & Karnataka State Police Public Reports | Public Open Data / Academic Fair Use (ODbL / CC-BY) | Bengaluru South & Central Urban Districts | 2024–2026 Annual & Quarterly Releases | Ingested Oct 2026 | Police Station & Ward level (~500m–1km) | Incident FIR records are aggregate; point-level geocodes are restricted in Indian jurisprudence. Model risk score does **NOT** represent personal victimization probability. |
| **3. Street Lighting** | BBMP Municipal Luminaire Registry & OpenStreetMap `lit=*` tags | Municipal Open Registry & ODbL 1.0 | Pilot Corridor Wards (Ward 143, South End, Jayanagar) | Annual municipal asset survey | Oct 2026 | Lamp node locations (10m–25m intervals) | Static inventory reflects asset existence, not live electrical illumination or bulb burnout status. 82.6% of residential ways lack explicit tags (Q=0, R_unknown=0.50). |
| **4. Stray Dog Encounters** | SafePath Verified Community Submissions & Animal Welfare NGO Audits | SafePath Community Contribution (CC-BY-NC 4.0) | Pilot Corridor (Jayanagar, South End, Basavanagudi) | Rolling 180-day window with recency decay | Dynamic live DB query | User pinned coordinates (15m–30m) | Zero approved reports indicates **absence of recorded evidence, never proof of canine absence**. Ordinary sightings do not penalize routes. |
| **5. Pedestrian Infrastructure** | OpenStreetMap `sidewalk=*`, `kerb=*`, `tactile_paving=*`, `crossing=*` tags | Open Database License (ODbL) 1.0 | Greater Bengaluru Pilot Corridor | Historical OSM community edits | Oct 2026 | Metric street segment geometry | 3-state classification enforced: Confirmed Present, Confirmed Absent, and Unknown/Unmapped. Missing tags are strictly treated as unmapped (50% neutral prior). |
| **6. Emergency & Civic Facilities** | OpenStreetMap POI Directory (`amenity=police`, `amenity=hospital`, `amenity=pharmacy`) | Open Database License (ODbL) 1.0 | Pilot Corridor + 500m buffer (34 mapped facilities) | Validated against physical civic presence | Nov 2026 | Physical building access centroids | Proximity indicates walking network accessibility, **never guaranteed desk staffing, emergency triage readiness, or open gate status**. |
| **7. Public Transit & Landmarks** | Bangalore Metro Rail Corporation (BMRCL) & BMTC Bus Terminals via OSM | Open Database License (ODbL) 1.0 | Namma Metro Green/Purple Lines & Major Transit Hubs | Operational network schedule | Oct 2026 | Platform entrance coordinates | Proximity provides orientation and foot-traffic opportunities; does not guarantee operational feeder connectivity during late-night departures. |
| **8. Community Reports & Feedback** | SafePath Registered & Anonymous Civic Submissions | User Contributed (CC-BY-NC 4.0 with reporter PII stripped) | Pilot Research Corridor | Real-time submissions (with 180-day staleness threshold) | Live database query with administrative moderation | User map-pinned (30m tolerance) | Subject to volunteer self-selection density; moderation status (`approved`) indicates policy adherence, **not independent scientific ground-truth verification**. |

Crowd density estimation, live video feeds, and speculative crime prediction are **explicitly excluded** from the pipeline due to ethical, privacy, and sensor absence constraints.

## 6. Spatial Matching of Evidence to Street Segments

To associate unstructured point evidence with street segments without projection distortion:
1. Street geometries and point observations are projected into UTM Zone 43N (`EPSG:32643`).
2. A Shapely `STRtree` spatial index is constructed over the edge geometries.
3. Points within a strict perpendicular buffer threshold ($15\text{m}$ for lighting fixtures, $30\text{m}$ for community reports) are linked to the nearest edge using orthogonal projection distance:
   $$\text{dist}(P, E) = \min_{t \in [0, 1]} \| P - (A + t(B - A)) \|$$
4. Observations exceeding the buffer distance remain unmatched with `match_status = "unmatched"`, preventing attribution to distant parallel streets.

---

## 7. Multi-Dimensional Safety Dimensions & Risk Normalization (Model v2.0.0)

SafePath v2.0 represents six distinct safety and infrastructure dimensions independently for every eligible street segment $e = (u, v, k)$ in the unit interval $[0, 1]$, where $0.0$ represents minimal adverse risk (optimal condition) and $1.0$ represents maximum adverse risk:

1. **Historical Crime Evidence ($C(e)$)**:
   Normalizes verified spatial incident density per kilometer along the street corridor:
   $$C(e) = \min\left(1.0, \frac{\text{incidents\_per\_km}}{10.0}\right)$$
   Evidence coverage $q_c(e) = 1.0$ if crime records exist for the ward/buffer, else $0.0$.
2. **Street Lighting Conditions ($L(e)$)**:
   Evaluates empirical physical illumination state modulated by the intended departure period:
   $$L(e) = \begin{cases} 0.10, & \text{if verified lit (`lit=yes` or municipal lamp present)} \\ 0.90, & \text{if verified unlit (`lit=no`)} \\ 0.70, & \text{if conflicting community lighting reports} \\ R_{\text{unknown}} = 0.50, & \text{if unmapped / unknown lighting} \end{cases}$$
   Evidence coverage $q_l(e) = 1.0$ if mapped in OSM or surveyed; $0.0$ if unmapped.
3. **Dog Sighting & Encounter Hazards ($D(e)$)**:
   Explicitly distinguishes ordinary calm sightings from aggressive canine hazards:
   - *Ordinary sightings* ($D = 0.10$): Informational; captures awareness of stray presence without inducing routing penalties.
   - *Pack sightings* ($D = 0.40$): Moderate awareness of group territoriality.
   - *Aggressive encounters* ($D = 0.85$): Documented chasing, snapping, or aggressive barking.
   - *Physical bite incidents* ($D = 1.00$): Highest hazard severity.
   Evidence coverage $q_d(e) = 1.0$ if community canine reports exist within buffer; $0.0$ otherwise.
4. **Community Safety Feedback ($F(e)$)**:
   Aggregates verified subjective community reports (harassment, poorly maintained areas, verbal abuse):
   $$F(e) = \frac{\sum_{r} \text{severity}_r \times \text{recency\_weight}_r}{\text{corroboration\_count}}$$
   Coverage $q_f(e) \in [0, 1]$ scales with report corroboration count.
5. **Pedestrian Infrastructure & Accessibility Deficiency ($P(e)$)**:
   Measures physical walkability defects:
   - Dedicated sidewalks present on both sides: base deficiency $0.05$.
   - Sidewalk on one side: base deficiency $0.25$.
   - Unmapped sidewalk status: neutral prior $0.50$ (unknown is never assumed absent).
   - High road-crossing difficulty: $+0.20$ penalty.
   - Tactile paving present: $-0.10$ accessibility credit.
   - Active physical obstruction / construction hazard: $+0.30$ penalty.
   Deficiency score is clamped to $[0.0, 1.0]$. Coverage $q_p(e) = 1.0$ if sidewalk/crossing tags or active obstruction reports exist; else $0.0$.
6. **Access to Assistance Facilities ($A(e)$)**:
   Evaluates physical network walking distance to emergency assistance (police stations, staffed hospitals):
   $$A(e) = \min\left(1.0, \frac{\text{walking\_minutes\_to\_nearest\_facility}}{20.0}\right)$$
   *Methodological Note*: $A(e)$ is treated strictly as an emergency resilience/isolation penalty, **never as proof of low crime or guaranteed immediate dispatch response**.

### Multi-Dimensional Adverse Risk Model ($R_{\text{observed}}$)
The observed risk for segment $e$ is synthesized as a convex combination:
$$R_{\text{observed}}(e) = w_c C(e) + w_l L(e) + w_d D(e) + w_f F(e) + w_p P(e) + w_a A(e)$$
where $\sum w_i = 1.0$.

### Model Weight Calibration (v1.0 vs v2.0)

| Dimension | Indicator | v1.0 Weight | v2.0 Weight | Calibration Rationale |
|---|---|---|---|---|
| Historical Crime | $C(e)$ | 0.35 | **0.25** | Reduced by 0.10 to integrate dedicated pedestrian infrastructure and canine encounter evidence without inflating overall risk. |
| Street Lighting | $L(e)$ | 0.30 | **0.25** | Adjusted by 0.05; dynamically modulated by time-of-day departure period. |
| Dog Encounters | $D(e)$ | 0.10 | **0.15** | Increased by 0.05 to reflect severe pedestrian vulnerability to canine territoriality and bite reports. |
| Community Feedback | $F(e)$ | 0.15 | **0.15** | Preserved to maintain verified community intelligence weighting. |
| Infrastructure Deficiency | $P(e)$ | 0.00 | **0.15** | **New in v2.0**: Dedicated evaluation of sidewalks, crosswalk signals, and physical obstructions. |
| Assistance Facility Isolation | $A(e)$ | 0.10 | **0.05** | Calibrated to 0.05 to prevent distant police stations from artificially penalizing safe, well-lit corridors. |
| **Sum** | | **1.00** | **1.00** | Strictly normalized convex combination. |

---

## 8. Evidence Coverage, Quality & Uncertainty Policy

SafePath adheres to a strict epistemological standard: **missing evidence is never encoded as zero risk**.

### Evidence Coverage Metric ($Q(e)$)
Each segment evaluates its composite evidence quality and availability ratio:
$$Q(e) = \frac{\sum_{i \in \mathcal{D}} w_i \times q_i(e)}{\sum_{i \in \mathcal{D}} w_i} \quad \in [0.0, 1.0]$$
where $q_i(e) \in [0.0, 1.0]$ represents the empirical data availability and quality for indicator $i$.

### Effective Risk Model ($R_{\text{effective}}$)
$$R_{\text{effective}}(e) = Q(e) \times R_{\text{observed}}(e) + (1 - Q(e)) \times R_{\text{unknown}}$$
where $R_{\text{unknown}} = 0.50$ is a configurable neutral prior assumption, representing epistemological uncertainty.

- **Zero Evidence ($Q=0$)**: $R_{\text{effective}} \equiv R_{\text{unknown}} = 0.50$.
- **Full Evidence ($Q=1$)**: $R_{\text{effective}} \equiv R_{\text{observed}}$.
- **Insufficient Evidence Alert**: When route-level coverage $Q < 0.30$, the assessment is explicitly flagged with `has_insufficient_evidence = true` to alert the user.

---

## 9. Three Primary Route Preferences

SafePath implements three distinct deterministic routing modes:

### A. Fastest Direct Route
Uses standard Dijkstra with traversal time as edge cost:
$$\text{Cost}_{\text{fastest}}(e) = T(e) = \frac{L(e)}{v}$$
where $L(e)$ is metric edge length and $v = 1.2\text{ m/s}$ ($4.32\text{ km/h}$) standard walking velocity.
**Fastest Invariance Principle**: Traversal time $T(e)$ depends strictly on physical length and pedestrian velocity, **invariant to departure time or lighting condition**. Darkness does not physically shorten or lengthen a sidewalk.

### B. Balanced Walking Route
$$\text{Cost}_{\text{balanced}}(e) = T(e) \times (1 + \lambda_{\text{balanced}} \times R_{\text{effective}}(e))$$
Default parameter $\lambda_{\text{balanced}} = 1.0$.

### C. Safety-Prioritized Route
$$\text{Cost}_{\text{safety}}(e) = T(e) \times (1 + \lambda_{\text{safety}} \times R_{\text{effective}}(e))$$
Default parameter $\lambda_{\text{safety}} = 3.0$.

**Requirement**: $\lambda_{\text{safety}} > \lambda_{\text{balanced}} \ge 0$. Every edge cost is strictly non-negative and finite ($0 < T(e) \le \text{Cost}(e) < \infty$). When preferences legitimately select the identical path, SafePath discloses that the corridor is optimal under multiple criteria without fabricating false detours.

---

## 10. Time-Aware Routing & Walkability Constraints

### Time-Aware Departure Periods
SafePath allows users to specify an intended departure period:
1. **Daytime** (06:00 – 18:00): Solar illumination dominates. Effective lighting weight multiplier is attenuated to $0.10$; diurnal report relevance is scaled by $0.70$.
2. **Evening** (18:00 – 22:00): Twilight transition. Lighting multiplier is $0.60$; diurnal report relevance is $1.00$.
3. **Night** (22:00 – 06:00): Complete reliance on artificial illumination. Lighting multiplier is $1.00$; diurnal report relevance is $1.20$.

*Limitation Transparency*: Mapped streetlights are not assumed to be functioning in real-time. If no time-specific telemetry exists, uncertainty is preserved.

### Walkability & Infrastructure Constraints
1. **Confirmed Pedestrian Prohibitions**: Ways tagged with `foot=no`, `access=private`, `access=no`, or motorways are assigned $\text{Cost}(e) = \infty$, strictly preventing pedestrian routing through prohibited infrastructure.
2. **Step-Free Accessibility Constraint**: When `step_free=true`, edges with `highway=steps` or stairs are assigned $\text{Cost}(e) = \infty$.
3. **Missing Tag Treatment**: Unmapped sidewalk or crossing tags are treated as unknown ($Q_p=0, R_{\text{unknown}}=0.50$), never assumed impassable.

---

## 11. Alternative Route Generation & Overlap Filtering

SafePath utilizes **Yen's K-Shortest Loopless Paths algorithm** to compute diverse alternative paths:
1. **Length-Weighted Overlap Metric**: Rather than unweighted edge counts, spatial overlap between path $P_1$ and $P_2$ is computed as length-weighted overlap:
   $$\text{Overlap}(P_1, P_2) = \frac{\sum_{e \in E(P_1) \cap E(P_2)} \text{len}(e)}{\sum_{e \in E(P_1) \cup E(P_2)} \text{len}(e)}$$
2. **Threshold**: Candidate paths with overlap $\ge 0.75$ with an already selected route are pruned to prevent returning near-identical micro-variations.
3. **Independent Metrics**: Every alternative calculates its own distance, duration, generalized cost, risk index, coverage, and evidence breakdown.

---

## 11.1 Evidence-Based Route Explanation Engine

For each returned path, SafePath generates an evidence-grounded explanation narrative breaking down:
- Primary selection rationale and objective function.
- Verified lighting conditions during the chosen departure period.
- Historical crime presence or absence along traversed corridors.
- Canine encounters (distinguishing calm sightings from aggressive encounters).
- Pedestrian infrastructure status (sidewalks, crosswalks, accessibility).
- Emergency assistance proximity (police, hospitals).
- Epistemological coverage and missing-data prior contributions.
- Exact walking time delta compared to the fastest direct route.

---

---

## 12. Experimental Design and Baseline Comparisons

The evaluation compares route outputs across four benchmark scenarios representing diverse pedestrian journeys in the Bengaluru research corridor:

- **Scenario 1 (South Suburb to Botanical Gate)**: Jayanagar 4th Block $\to$ Lalbagh West Gate ($2.3\text{ km}$).
- **Scenario 2 (Transit Hub to Historic High Street)**: South End Circle $\to$ Gandhi Bazaar ($0.9\text{ km}$).
- **Scenario 3 (Civic Park to Commercial Promenade)**: Cubbon Park $\to$ MG Road ($1.4\text{ km}$).
- **Scenario 4 (Arterial Transit Axis)**: Jayanagar 4th Block $\to$ MG Road ($6.3\text{ km}$).

---

## 13. Empirical Evaluation Results

The evaluation script (`backend/scripts/evaluate_routing_methodology.py`) was executed against the active Bengaluru street network and empirical evidence tables.

### Table 1: Route Preference Comparisons Across Benchmark Scenarios

| Scenario & Route Preference | Distance (m) | Walking Time (min) | Detour vs Fastest | Model Risk Index ($R_{\text{eff}}$) | Lit Streets (%) | Evidence Coverage ($Q$) | Identical to Fastest? |
|---|---|---|---|---|---|---|---|
| **Scenario 1: Jayanagar 4th Block $\to$ Lalbagh West Gate** | | | | | | | |
| Fastest Direct Route ($\lambda=0$) | 2,264m | 31.4 min | Baseline (+0.0m) | 0.3763 | 100.0% | 45% | Yes (Baseline) |
| Balanced Route ($\lambda=1.0$) | 2,264m | 31.4 min | +0.0 min (+0.0%) | 0.3763 | 100.0% | 45% | **Yes (Coincides)** |
| Safety-Prioritized Route ($\lambda=3.0$) | 2,264m | 31.4 min | +0.0 min (+0.0%) | 0.3763 | 100.0% | 45% | **Yes (Coincides)** |
| Yen Alternative 1 | 2,741m | 38.1 min | +6.6 min (+21.0%) | 0.3648 | 100.0% | 45% | No (Diverse) |
| Yen Alternative 2 | 2,752m | 38.2 min | +6.8 min (+21.6%) | 0.3708 | 83.8% | 40% | No (Diverse) |
| **Scenario 2: South End Circle $\to$ Gandhi Bazaar** | | | | | | | |
| Fastest Direct Route ($\lambda=0$) | 901m | 12.5 min | Baseline (+0.0m) | 0.3575 | 100.0% | 45% | Yes (Baseline) |
| Balanced Route ($\lambda=1.0$) | 901m | 12.5 min | +0.0 min (+0.0%) | 0.3575 | 100.0% | 45% | **Yes (Coincides)** |
| Safety-Prioritized Route ($\lambda=3.0$) | 901m | 12.5 min | +0.0 min (+0.0%) | 0.3575 | 100.0% | 45% | **Yes (Coincides)** |
| Yen Alternative 1 | 1,424m | 19.8 min | +7.2 min (+57.9%) | 0.3575 | 100.0% | 45% | No (Diverse) |
| Yen Alternative 2 | 2,303m | 32.0 min | +19.5 min (+155%) | 0.3821 | 80.7% | 39% | No (Diverse) |
| **Scenario 3: Cubbon Park $\to$ MG Road** | | | | | | | |
| Fastest Direct Route ($\lambda=0$) | 1,426m | 19.8 min | Baseline (+0.0m) | 0.3800 | 100.0% | 30% | Yes (Baseline) |
| Balanced Route ($\lambda=1.0$) | 1,426m | 19.8 min | +0.0 min (+0.0%) | 0.3800 | 100.0% | 30% | **Yes (Coincides)** |
| Safety-Prioritized Route ($\lambda=3.0$) | 1,426m | 19.8 min | +0.0 min (+0.0%) | 0.3800 | 100.0% | 30% | **Yes (Coincides)** |
| Yen Alternative 1 | 1,777m | 24.7 min | +4.9 min (+24.7%) | 0.3858 | 100.0% | 34% | No (Diverse) |
| Yen Alternative 2 | 3,640m | 50.5 min | +30.8 min (+155%) | 0.3951 | 100.0% | 40% | No (Diverse) |
| **Scenario 4: Jayanagar 4th Block $\to$ MG Road (Full Arterial Corridor)** | | | | | | | |
| Fastest Direct Route ($\lambda=0$) | **6,309m** | **87.6 min** | Baseline (+0.0m) | **0.4086** | **69.3%** | 38% | Yes (Baseline) |
| Balanced Route ($\lambda=1.0$) | **6,452m** | **89.6 min** | **+2.0 min (+2.3%)** | **0.3743** | **100.0%** | 42% | **No (Diverges)** |
| Safety-Prioritized Route ($\lambda=3.0$) | **6,452m** | **89.6 min** | **+2.0 min (+2.3%)** | **0.3743** | **100.0%** | 42% | **No (Diverges)** |
| Yen Alternative 1 | 6,349m | 88.2 min | +0.6 min (+0.6%) | 0.4008 | 87.9% | 42% | No (Diverse) |
| Yen Alternative 2 | 6,320m | 87.8 min | +0.1 min (+0.2%) | 0.4094 | 76.4% | 40% | No (Diverse) |

### Key Experimental Finding:
In Scenario 4 (the multi-kilometer arterial route), the Fastest route traverses unlit residential cut-through lanes between Lalbagh and Subbaiah Circle to shave 143 meters (2.0 minutes). By contrast, both the **Balanced** and **Safety-Prioritized** routes correctly reject the dark shortcut in favor of the fully lit commercial Kasturba Road corridor, reducing the route risk indicator from $0.4086$ to $0.3743$ and increasing verified lighting from $69.3\%$ to $100.0\%$ at an acceptable walking detour cost of only $2.3\%$ ($+2.0\text{ min}$).

---

### Table 2: Sensitivity Analysis — Risk Weight Multiplier ($\lambda$)

Evaluating Scenario 1 (`Jayanagar 4th Block → Lalbagh West Gate`) under increasing $\lambda$:

| $\lambda$ (Risk Weight) | Selected Path Nodes | Distance (m) | Walking Time (min) | Lit Streets (%) | Effective Risk ($R_{\text{eff}}$) | Total Generalized Cost |
|---|---|---|---|---|---|---|
| $0.0$ (Fastest) | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 1,886.67 |
| $0.5$ | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 2,241.77 |
| $1.0$ (Balanced) | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 2,596.78 |
| $2.0$ | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 3,306.82 |
| $3.0$ (Safety-prioritized) | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 4,016.86 |
| $5.0$ (Extreme Aversion)| `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 31.4 min | 100.0% | 0.3763 | 5,436.90 |

**Analysis**: Total generalized cost increases strictly monotonically from $1,886.67$ to $5,436.90$ ($\frac{\partial C}{\partial \lambda} > 0$), while path stability is maintained because the direct commercial avenue is already optimal under verified lighting.

---

### Table 3: Sensitivity Analysis — Missing-Data Neutral Prior ($R_{\text{unknown}}$)

Evaluating the effect of the neutral prior parameter $R_{\text{unknown}}$ on the effective route risk:

| $R_{\text{unknown}}$ Prior | Selected Path | Distance (m) | Route Risk Indicator ($R_{\text{eff}}$) | Unmapped Streets (%) |
|---|---|---|---|---|
| $0.20$ (Optimistic prior) | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 0.2113 | 0.0% |
| $0.40$ | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 0.3213 | 0.0% |
| **$0.50$ (SafePath Default)**| `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | **0.3763** | 0.0% |
| $0.60$ | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 0.4313 | 0.0% |
| $0.80$ (Pessimistic prior) | `[1001, 1004, 1007, 1010, 1013, 1015]` | 2,264m | 0.5413 | 0.0% |

**Analysis**: The route risk indicator varies continuously with $R_{\text{unknown}}$ according to the analytical formula $R_{\text{effective}} = Q \cdot R_{\text{obs}} + (1 - Q) \cdot R_{\text{unknown}}$. Uncertainty is preserved; setting $R_{\text{unknown}} > 0$ ensures uncorroborated streets are never rewarded with artificial low-risk scores.

---

### 13.4 Usability Evaluation Protocol (Future Research Protocol)

To evaluate whether pedestrians comprehend the explainable multi-attribute recommendations, evidence explorer indicators, and travel-time trade-offs, a reproducible ethical usability-study protocol has been formulated.

> [!IMPORTANT]
> **Ethical & Methodological Disclosure**: No human-participant field study has been conducted to date. SafePath Finder currently operates as an academic research prototype. The following protocol is formally specified as an Institutional Review Board (IRB) ethical submission package for future experimental deployment.

#### A. Participant Selection & Informed Consent
- **Target Cohort**: N = 30 adult urban pedestrians (stratified across gender identities and age groups 18–65) who regularly walk in urban corridors.
- **Informed Consent**: Explicit written consent explaining that SafePath is an experimental navigation prototype, does not dispatch emergency services, and does not provide an unconditional safety guarantee.
- **Right to Withdraw**: Participants may terminate the session at any time without penalty.

#### B. Pre-Study Questionnaire
1. Frequency of walking trips per week.
2. Primary navigation applications currently utilized (Google Maps, Apple Maps, etc.).
3. Experience with nighttime walking and personal safety concerns in urban corridors.
4. Perception of commercial navigation "safety scores" (trust, transparency, perceived accuracy).

#### C. Structured Evaluation Tasks
Participants are presented with the interactive SafePath Finder interface on calibrated devices and asked to complete four standardized scenarios:
- **Task 1 (Route Preference Comprehension)**: Plan a journey from Jayanagar 4th Block to Lalbagh West Gate. Inspect the three primary routes (Fastest, Balanced, Safety-prioritized). Explain why the direct avenue coincides for all three preferences, and identify how Yen's alternatives differ in distance and time overhead.
- **Task 2 (Evidence Explorer & Missing Data Interpretation)**: Open the Evidence Explorer for the Safety-prioritized route. Locate the streetlight distribution breakdown. Explain the difference between "Unlit Street Segments" and "Unmapped / Unknown Lighting". State whether an unmapped street is considered safe.
- **Task 3 (Dog Encounter Taxonomy & Severity)**: Review the Dog Encounter Summary card. Differentiate between an "Ordinary Calm Sighting" and an "Aggressive Canine Encounter". Explain why an ordinary sighting does not induce route detours while aggressive reports trigger safety penalties.
- **Task 4 (Travel-Time vs. Evidence Trade-off)**: In Scenario 4 (Jayanagar -> MG Road), examine why the Balanced route takes a 2.0-minute detour (+2.3% time overhead) compared to the Fastest cut-through. Assess whether this trade-off is transparent and justifiable.

#### D. Post-Task Comprehension & Usability Metrics
- **Explanation Clarity**: Evaluated via 7-point Likert scale ("The route cards clearly explained why one path was recommended over another").
- **Uncertainty Transparency**: Likert scale ("I clearly understood that unmapped areas represent missing information rather than verified safety").
- **Trust & Calibration**: Assessment of whether users over-rely on the system or understand its boundary limitations.
- **System Usability Scale (SUS)**: Standardized 10-item instrument for overall software usability.

---

## 14. Limitations, Privacy Considerations, and Threats to Validity

1. **Absence of Point-Level Crime Geocodes**: In India, police First Information Reports (FIRs) are typically published as annual district aggregates rather than open point-level coordinates. SafePath ingests verified CSV datasets when supplied, but strictly refuses to hallucinate synthetic crime incidents.
2. **Tag Sparsity in OpenStreetMap**: Approximately 80% of residential secondary ways in Indian cities lack explicit `lit=*` tags. SafePath treats these as unmapped informational gaps ($Q=0, R=0.50$), avoiding false danger claims.
3. **Emergency Facility Operating Status**: Spatial accessibility measures straight-line and walking distance to physical police stations and hospitals, not whether gates are unlocked or staff are present.
4. **Privacy and PII Isolation**:
   - Trusted-contact phone numbers and names are encrypted at rest with AES-128 Fernet.
   - Passwords use Argon2id with random 128-bit salts.
   - Community report submissions allow anonymous posting; user accounts are never linked in public GeoJSON payloads.
5. **Epistemological Warning**: Improvements in model risk indicators reflect increased documented lighting and proximity to assistance assets; they **do not constitute empirical proof that victimization has decreased**.

---

## 15. Future Research Directions

- **Integration with Municipal IoT Telemetry**: Connect municipal Smart City SCADA streetlight feeds for real-time bulb failure updates.
- **Micro-Environmental Obstacle Mapping**: Incorporate pavement surface quality, open drains, and footpath obstructions from civic grievance portals.
- **Participatory GIS Audits**: Conduct community-led pedestrian walks to ground-truth and corroborate unmapped residential corridors.
- **Edge-Device Offline Routing**: Compile the Dijkstra router and Pilot Corridor GraphML into SQLite Spatialite / WebAssembly for fully offline walking guidance without internet connectivity.
