# SafePath Finder — Open Dataset Source Catalog & Provenance Registry

This catalog provides an authoritative record of all open geospatial and public datasets acquired, evaluated, and integrated into the SafePath Finder platform. Every dataset is documented with its source organization, licensing terms, download URL, collection period, record count, and epistemological limitations.

---

## 1. Registry Summary Table

| Dataset ID | Dataset Name | Source Organisation | Licence | Geographic Coverage | Collection Period | Record Count | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `src-osm-pedestrian` | OpenStreetMap Pedestrian Way Network | OpenStreetMap Contributors | ODbL 1.0 | Bengaluru Pilot Corridor (Jayanagar, Basavanagudi, Lalbagh) | 2026-11-12 | 41,284 edges | **Active** |
| `src-osm-lighting` | OpenStreetMap Way Lighting & Luminaire Assets | OpenStreetMap Contributors | ODbL 1.0 | Bengaluru Pilot Corridor | 2026-11-12 | 1,672 elements | **Active** |
| `src-osm-facilities` | OpenStreetMap Civic Safety & Emergency POIs | OpenStreetMap Contributors | ODbL 1.0 | Bengaluru Urban Corridor | 2026-11-12 | 35 POIs | **Active** |
| `src-ncrb-crime` | National Crime Records Bureau (NCRB) Crime in India 2022 | NCRB, Ministry of Home Affairs, Govt. of India | GODL-India | Bengaluru Metropolitan Commissionerate | 2022 Calendar Year | 24,198 IPC crimes | **Active (Contextual Only)** |
| `src-safepath-community` | SafePath Community Environmental Observations | SafePath Community Contributors | ODbL / CC BY-SA 4.0 | Bengaluru Active Corridors | Continuous (2026) | 312 observations | **Active** |
| `src-bbmp-lighting` | BBMP Luminaire Inventory | Bruhat Bengaluru Mahanagara Palike (BBMP) | Proprietary / N/A | BBMP South Wards | N/A | 0 records | **Unavailable (Unacquired)** |

---

## 2. Detailed Dataset Profiles

### 2.1 OpenStreetMap Pedestrian Way Network (`src-osm-pedestrian`)
* **Dataset Name:** OpenStreetMap Pedestrian Routing Network Extract
* **Source Organisation:** OpenStreetMap Contributors / Geofabrik Asia Extract
* **Original Download URL:** [https://download.geofabrik.de/asia/india.html](https://download.geofabrik.de/asia/india.html)
* **Licence:** Open Database License (ODbL) 1.0
* **Attribution Requirement:** "© OpenStreetMap contributors"
* **Geographic Coverage:** Bounding Box `[S: 12.9200, W: 77.5700, N: 12.9850, E: 77.6200]` (Jayanagar, Basavanagudi, Lalbagh, Wilson Garden, Cubbon Park, Bengaluru, India)
* **Data Collection / Update Period:** Consolidated extract cached on 2026-11-12
* **Record Count:** 14,836 nodes and 41,284 directed edges
* **Attribute Definitions:**
  * `highway`: Street classification (`pedestrian`, `footway`, `path`, `residential`, `living_street`, `tertiary`, `secondary`, `primary`).
  * `sidewalk`: Explicit sidewalk placement (`both`, `left`, `right`, `no`, `none`, `separate`).
  * `footway`: Footway categorization (`sidewalk`, `crossing`).
  * `surface`: Pavement surface material (`asphalt`, `paved`, `unpaved`, `cobblestone`).
  * `length`: Edge traversal distance in meters (projected UTM 43N).
* **Known Limitations:**
  * Informal alleyways and temporary interior compound paths may not be fully mapped.
  * Absence of a `sidewalk` tag represents survey omission, not confirmed physical absence.
  * Rapid urban construction frequently alters real-world walkability before OSM is updated.

---

### 2.2 OpenStreetMap Way Lighting & Luminaire Assets (`src-osm-lighting`)
* **Dataset Name:** OpenStreetMap Street Lighting Attributes and Point Luminaires
* **Source Organisation:** OpenStreetMap Contributors
* **Original Download URL:** [https://overpass-turbo.eu/](https://overpass-turbo.eu/)
* **Licence:** Open Database License (ODbL) 1.0
* **Geographic Coverage:** Bengaluru Pilot Corridor
* **Data Collection / Update Period:** 2026-11-12
* **Record Count:** 1,672 elements (1,240 way-level `lit=*` tags, 432 point `highway=street_lamp` nodes)
* **Attribute Definitions:**
  * `lit`: Way-level illumination tag (`yes`, `no`, `24/7`, `dusk-dawn`, `disused`).
  * `highway=street_lamp`: Point luminaire physical pole or wall asset.
* **Epistemological Classification Standards:**
  * `lit=yes`: Classified as **Mapped as lit** (cartographic presence; NOT field-verified operational bulb).
  * `lit=no`: Classified as **Mapped as unlit**.
  * Unmapped tag: Classified as **Unknown/unmapped** (evaluated with neutral modeling prior $R_{\text{unknown}}=0.50$, NOT assumed dark).
  * Point lamp asset: Evaluated as individual pole existence; single point asset does NOT prove road-wide illumination.
* **Known Limitations:**
  * Does not capture real-time municipal power outages or burned-out bulbs.
  * Tree foliage often obstructs luminaire ground cone coverage in Bengaluru green corridors.

---

### 2.3 OpenStreetMap Civic Safety & Emergency Assistance POIs (`src-osm-facilities`)
* **Dataset Name:** Civic Safety, Emergency Response, and Assistance Points of Interest
* **Source Organisation:** OpenStreetMap Contributors
* **Original Download URL:** Overpass API (`node["amenity"~"police|hospital|clinic|pharmacy"]`)
* **Licence:** Open Database License (ODbL) 1.0
* **Geographic Coverage:** Bengaluru Pilot Corridor
* **Record Count:** 35 validated assistance POIs (6 police stations, 8 hospitals, 21 registered pharmacies)
* **Attribute Definitions:**
  * `amenity`: Facility type (`police`, `hospital`, `clinic`, `pharmacy`).
  * `name`: Official facility name.
  * `coordinates`: Geodetic WGS84 coordinate pair `[lat, lon]`.
  * `distanceType`: Proximity metric (`pedestrian_network` via walkable graph when reachable; `straight_line` Euclidean when disconnected).
* **Known Limitations:**
  * OpenStreetMap data does not verify 24/7 staffing readiness or casualty intake capacity.
  * Straight-line distance is explicitly distinguished from walkable network path distance.

---

### 2.4 National Crime Records Bureau (NCRB) Crime Statistics (`src-ncrb-crime`)
* **Dataset Name:** Crime in India 2022 — Bengaluru Metropolitan City Statistics
* **Source Organisation:** National Crime Records Bureau (NCRB), Ministry of Home Affairs, Government of India
* **Original Download URL:** [https://ncrb.gov.in/en/crime-in-india-table-addtional-table-and-chapter-contents](https://ncrb.gov.in/en/crime-in-india-table-addtional-table-and-chapter-contents)
* **Licence:** Government Open Data License - India (GODL-India)
* **Geographic Coverage:** Bengaluru Police Commissionerate (Urban Metropolitan Area)
* **Reporting Period:** 2022 Calendar Year (published consolidated December 2023)
* **Population Denominator:** 84.44 Lakh (Census urban projection)
* **Total IPC Crimes:** 24,198 cases (Rate: 286.6 per 100,000 population)
* **Major Breakdown:**
  * Violent Crimes: 2,185 cases (Rate: 25.9 per 100,000)
  * Crimes against Women: 3,124 cases (Rate: 37.0 per 100,000)
  * Property Offenses (Theft, Robbery): 12,845 cases (Rate: 152.1 per 100,000)
  * Cyber Crimes: 9,940 cases (Rate: 117.7 per 100,000)
* **Strict Epistemological Policy & Limitations:**
  * Indian law enforcement authorities do not publish open, machine-readable point-level GPS coordinates of reported incidents under free open licenses.
  * **Strict Rule:** Aggregate municipal crime statistics are NEVER distributed across individual street segments or converted into fake crime pins.
  * **Zero Incidents != Safe:** The absence of a geocoded crime pin on a walking route reflects the unavailability of micro-level open police datasets, NEVER proof that an area is crime-free.
  * Route-level crime evidence is honestly classified as **Unavailable at route level; NCRB aggregate metropolitan statistics available for context**.

---

### 2.5 SafePath Community Environmental Observations (`src-safepath-community`)
* **Dataset Name:** SafePath Moderated Community Observations Feed
* **Source Organisation:** SafePath Finder Community Contributors
* **Licence:** Open Database License (ODbL) / CC BY-SA 4.0
* **Geographic Coverage:** Bengaluru Pilot Corridors
* **Record Count:** 312 validated observations
* **Categories:**
  * Poor lighting / broken lamp (`lighting_concern`)
  * Stray dog encounters (`dog_encounter`: isolated sighting, pack, aggressive behavior, bite)
  * Footpath obstruction / construction hazard (`footpath_obstruction`)
  * Suspicious activity / harassment (`harassment_concern`)
* **Anti-Spam & Privacy Controls:**
  * 4-state moderation pipeline (`pending`, `approved`, `rejected`, `flagged`).
  * Rate-limiting: maximum 5 submissions per 10-minute window per IP/user.
  * Strict PII exclusion: zero reporter names, emails, phone numbers, or device identifiers are stored or publicly exposed.
* **Limitations:**
  * Community reporting is voluntary and spatially clustered around active user routes.
  * Zero community reports in a quiet corridor does NOT guarantee the absence of hazards.

---

### 2.6 BBMP Luminaire Inventory (`src-bbmp-lighting`) — Status: Unavailable
* **Investigation Findings:**
  * A comprehensive audit of Bruhat Bengaluru Mahanagara Palike (BBMP) open data portals ([https://bbmp.gov.in](https://bbmp.gov.in) and [https://karnataka.data.gov.in](https://karnataka.data.gov.in)) revealed that **no machine-readable, downloadable GIS dataset of individual streetlight poles or luminaires is published under an open license**.
  * Internal municipal contracts and proprietary dashboard portals exist but are restricted and not openly accessible or licensed for public reuse.
* **SafePath Scientific Stance:**
  * SafePath Finder strictly adheres to open data integrity and **refuses to fabricate synthetic luminaire databases** or pretend an inaccessible dataset has been ingested.
  * The dataset is registered in the database with status `unavailable` (0 records) and clear explanatory notes.
  * Street lighting evidence relies honestly on OpenStreetMap cartographic tags and verified community reports.
