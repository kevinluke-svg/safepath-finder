# SafePath Finder — Research Methodology & Routing Engine Evaluation

**Document Version:** 1.0.0  
**Research Domain:** Human-Centred Geospatial Systems, Evidence-Based Pedestrian Navigation, Women's Walking Mobility  
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

## 5. Evidence Sources and Data Preparation

The platform integrates four evidence channels:

| Evidence Type | Upstream Source | Attribute Evaluated | Licensing & Attribution | Limitations |
|---|---|---|---|---|
| **Street Lighting** | OpenStreetMap ways & nodes | `lit=yes/no`, `highway=street_lamp` | Open Database Licence (ODbL) 1.0 | High municipal unmapped rate (~82.6% in pilot bbox) |
| **Emergency Facilities** | OpenStreetMap POIs | `amenity=police`, `amenity=hospital/clinic` | ODbL 1.0 | Proximity reflects network access, not confirmed open reception |
| **Historical Crime** | Verified District / Ward Records | Normalized incident rate per km | Documented Dataset (ODbL / CC-BY) | Point-level geocodes are restricted in India; ward aggregates applied |
| **Community Feedback** | SafePath Verified Submissions | Street observation category, ratings | User Contributed (SafePath CC-BY-NC) | Subject to volunteer self-selection and reporting density |

Crowd density estimation and speculative pedestrian counts are **explicitly excluded** from the pipeline due to the absence of ground-truth sensor coverage.

---

## 6. Spatial Matching of Evidence to Street Segments

To associate unstructured point evidence with street segments without projection distortion:
1. Street geometries and point observations are projected into UTM Zone 43N (`EPSG:32643`).
2. A Shapely `STRtree` spatial index is constructed over the edge geometries.
3. Points within a strict perpendicular buffer threshold ($15\text{m}$ for lighting fixtures, $30\text{m}$ for community reports) are linked to the nearest edge using orthogonal projection distance:
   $$\text{dist}(P, E) = \min_{t \in [0, 1]} \| P - (A + t(B - A)) \|$$
4. Observations exceeding the buffer distance remain unmatched with `match_status = "unmatched"`, preventing attribution to distant parallel streets.

---

## 7. Risk Indicators and Normalization

Each street edge $e = (u, v, k)$ is evaluated across four normalized sub-indicators in the unit interval $[0, 1]$, where $0.0$ represents minimal observed risk (best environmental condition) and $1.0$ represents maximum observed risk:

1. **Lighting Risk ($R_{\text{lit}}$)**:
   $$R_{\text{lit}} = \begin{cases} 0.10, & \text{if explicitly lit } (\text{`lit=yes` or municipal lamp present}) \\ 0.90, & \text{if explicitly unlit } (\text{`lit=no`}) \\ 0.70, & \text{if conflicting community reports} \\ R_{\text{unknown}} = 0.50, & \text{if unmapped / unknown} \end{cases}$$
2. **Crime Incident Rate ($R_{\text{crime}}$)**:
   $$R_{\text{crime}} = \min\left(1.0, \frac{\text{incidents\_per\_km}}{10.0}\right)$$
3. **Emergency Facility Proximity ($R_{\text{assist}}$)**:
   $$R_{\text{assist}} = \min\left(1.0, \frac{\text{walking\_minutes\_to\_nearest\_facility}}{20.0}\right)$$
4. **Community Feedback Risk ($R_{\text{comm}}$)**:
   Derived from negative street reports normalized against corroboration counts.

Sub-indicators are aggregated using configured multi-criteria utility weights:
$$R_{\text{observed}} = w_{\text{crime}} R_{\text{crime}} + w_{\text{lit}} R_{\text{lit}} + w_{\text{assist}} R_{\text{assist}} + w_{\text{comm}} R_{\text{comm}}$$
Default research weights: $w_{\text{crime}} = 0.35, w_{\text{lit}} = 0.35, w_{\text{assist}} = 0.15, w_{\text{comm}} = 0.15$ ($\sum w_k = 1.0$).

---

## 8. Missing-Data and Uncertainty Policy

SafePath's defining research differentiator is the **honesty principle regarding missing information**:

### Evidence Coverage Metric ($Q$)
Each segment computes its evidence completeness ratio:
$$Q_e = \sum_{k \in \mathcal{K}_{\text{available}}} w_k \quad \in [0, 1]$$
where $\mathcal{K}_{\text{available}}$ denotes the subset of indicators with documented upstream observations.

### Effective Segment Risk ($R_{\text{effective}}$)
Rather than assuming missing data indicates safety ($R=0$), SafePath preserves an epistemological neutral prior ($R_{\text{unknown}} = 0.50$):
$$R_{\text{effective}}(e) = Q_e \cdot R_{\text{observed}}(e) + (1 - Q_e) \cdot R_{\text{unknown}}$$

### Properties:
- **Zero Evidence**: When $Q_e = 0$, $R_{\text{effective}}(e) \equiv R_{\text{unknown}} = 0.50$.
- **Complete Evidence**: When $Q_e = 1.0$, $R_{\text{effective}}(e) \equiv R_{\text{observed}}(e)$.
- **Insufficient Evidence Alert**: If $Q_e < 0.30$, the segment is flagged with `has_insufficient_evidence = true`, prompting an explicit amber warning on the user interface.

---

## 9. Dijkstra Algorithm for Fastest Routing

The **Fastest Route** preference minimizes estimated walking traversal time without environmental risk weighting:
$$\text{Cost}_{\text{fastest}}(e) = T_e = \frac{L_e}{v}$$
where $L_e$ is the edge metric length and $v = 1.2\text{ m/s}$ ($4.32\text{ km/h}$) is standard walking velocity.

Because all edge lengths $L_e > 0$, the edge traversal times are strictly positive ($T_e > 0$). Standard Dijkstra shortest-path execution guarantees finding the global minimum walking duration path between origin and destination nodes.

---

## 10. Generalized Edge-Cost Formula for Balanced and Safety-Prioritized Routing

For risk-aware preferences, the edge cost incorporates an additive penalty proportional to the risk indicator:

$$C(e) = T_e \cdot \left(1 + \lambda \cdot R_{\text{effective}}(e)\right)$$

where $\lambda \ge 0$ is the **risk-aversion multiplier**:
- **Fastest Direct Route**: $\lambda = 0.0 \implies C(e) = T_e$.
- **Balanced Walking Route**: $\lambda_{\text{balanced}} = 1.0 \implies C(e) = T_e \cdot (1 + R_{\text{effective}})$.
- **Safety-Prioritized Route**: $\lambda_{\text{safety}} = 3.0 \implies C(e) = T_e \cdot (1 + 3 R_{\text{effective}})$.

### Mathematical Guarantees:
1. **Strict Positivity & Finiteness**: Because $T_e > 0$, $\lambda \ge 0$, and $R_{\text{effective}} \in [0, 1]$, every edge cost satisfies:
   $$0 < T_e \le C(e) \le T_e(1 + \lambda) < \infty$$
2. **Monotonicity with Risk Weight**:
   $$\frac{\partial C(e)}{\partial \lambda} = T_e \cdot R_{\text{effective}}(e) \ge 0$$
   Total path cost strictly increases as risk weight $\lambda$ increases.
3. **Detour Constraint**: Routes exceeding a maximum detour ratio ($1.40 \times \text{Fastest Duration}$) are flagged with an explicit limitation note.

---

## 11. Alternative-Route Generation Method

SafePath uses **Yen's K-Shortest Loopless Paths algorithm** to compute genuine alternatives that provide path diversity without loops:

1. **Algorithm Execution**: A simplified directed graph is constructed with edge weights set to the Balanced generalized cost. Yen's algorithm (`nx.shortest_simple_paths`) generates candidate paths in non-decreasing order of generalized cost.
2. **Loopless Guarantee**: Yen's algorithm searches exclusively over simple (loopless) paths; no node is visited more than once.
3. **Jaccard Edge Overlap Filtering**: To eliminate trivial variations (e.g. crossing to an opposite sidewalk mid-block), candidate paths must have an edge-overlap ratio below the threshold ($\theta = 0.80$) compared to previously selected paths:
   $$\text{Overlap}(P_1, P_2) = \frac{|E(P_1) \cap E(P_2)|}{|E(P_1) \cup E(P_2)|} < 0.80$$
4. **Identical Path Transparency**: When the physically shortest avenue is *also* the most brightly illuminated and best serviced corridor, both Balanced and Safety-prioritized Dijkstra runs will select the identical path as the Fastest route. SafePath flags this state (`isIdenticalToFastest = true`) and displays:
   > *"Optimal under multiple criteria: this path is already the fastest while maximizing verified lighting; no detour needed."*
   Artificial diversity is never fabricated.

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
