import re

with open("RESEARCH_METHODOLOGY.md", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Expand Section 5 to full 8-source Data Source Audit
sec5_replacement = r"""## 5. Evidence Sources and Comprehensive Data Source Audit

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

Crowd density estimation, live video feeds, and speculative crime prediction are **explicitly excluded** from the pipeline due to ethical, privacy, and sensor absence constraints."""

content = re.sub(r'## 5\. Evidence Sources and Data Preparation.*?(?=## 6\.)', lambda m: sec5_replacement + "\n\n", content, flags=re.DOTALL)

# 2. Add Usability Evaluation Protocol under Section 13
usability_protocol = r"""### 13.4 Usability Evaluation Protocol (Future Research Protocol)

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
- **System Usability Scale (SUS)**: Standardized 10-item instrument for overall software usability."""

content = re.sub(r'(## 14\. Limitations, Privacy Considerations, and Threats to Validity)', lambda m: usability_protocol + "\n\n---\n\n" + m.group(1), content)

with open("RESEARCH_METHODOLOGY.md", "w", encoding="utf-8") as f:
    f.write(content)

print("RESEARCH_METHODOLOGY.md updated successfully!")
