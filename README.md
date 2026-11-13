# SafePath Finder — Explainable Walking Navigation Platform

A human-centred, research-grade walking navigation platform for evaluating pedestrian route context with transparent evidence quality, street-segment inspection, and explicit uncertainty indicators.

SafePath is built on the core epistemological principle that **evidence availability is not the same as personal safety**, and that an absence of incident reports or unmapped areas must **never be encoded as low risk**.

---

## 1. System Architecture & Tech Stack

SafePath Finder comprises an accessible, zero-build frontend paired with a modular Python/FastAPI backend conforming strictly to [`API_CONTRACT.md`](file:///home/kevinluke/safe%20path/API_CONTRACT.md) under `/api/v1`.

```
safe path/
├── backend/                           # Python FastAPI Backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                # JWT auth, user resolution & role gates
│   │   │   └── v1/                    # REST endpoints matching API_CONTRACT.md
│   │   │       ├── auth.py            # Argon2id registration, login, reset, /me
│   │   │       ├── routes.py          # Multi-attribute route ranking & /study-area
│   │   │       ├── evidence.py        # Street segment provenance & uncertainty
│   │   │       ├── reports.py         # Community reports & auto-flagging
│   │   │       ├── journeys.py        # Saved journeys, history & places
│   │   │       ├── contacts.py        # Encrypted trusted contacts & dispatch status
│   │   │       ├── feedback.py        # User feedback & administrative inbox
│   │   │       ├── admin.py           # Moderation queue, privacy-minimized users, identity reveal, audit
│   │   │       └── __init__.py        # Combined v1 router
│   │   ├── geospatial/                # Geospatial routing foundation & data adapters
│   │   │   ├── exceptions.py          # Domain boundary & coordinate exceptions
│   │   │   ├── study_area.py          # StudyArea definition & coordinate bounds validation
│   │   │   ├── network_adapter.py     # OSMnx pedestrian network retrieval & GraphML caching
│   │   │   ├── lighting_adapter.py    # OSM lighting tags & uncertainty classification
│   │   │   ├── facilities_adapter.py  # Police vs healthcare POIs (strictly separated)
│   │   │   ├── crime_adapter.py       # Validated CSV crime ingestion & PII exclusion
│   │   │   ├── community_adapter.py   # Database community reports (PII stripped)
│   │   │   └── __init__.py            # Exported adapters and interfaces
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic v2 Settings & environment parsing
│   │   │   ├── security.py            # Argon2id password hashing & PyJWT tokens
│   │   │   └── encryption.py          # AES-128 Fernet field encryption & data masking
│   │   ├── db/
│   │   │   ├── session.py             # SQLAlchemy 2.0 session & SQLite PRAGMA
│   │   │   └── seed.py                # Demonstration fixtures for pilot corridor
│   │   ├── models/                    # Declarative SQLAlchemy ORM models
│   │   │   ├── user.py                # Users & roles (traveller, moderator, admin)
│   │   │   ├── report.py              # Community reports & 4-state moderation
│   │   │   ├── journey.py             # Saved plans, history, saved places
│   │   │   ├── contact.py             # Encrypted contacts, journey shares, arrival pings
│   │   │   ├── feedback.py            # User feedback submissions & admin notes
│   │   │   ├── password_reset.py      # Expiring single-use reset tokens (hashed at rest)
│   │   │   ├── evidence.py            # Upstream data sources & street segments
│   │   │   ├── audit.py               # Append-only governance audit log
│   │   │   └── settings.py            # Dynamic thresholds & auto-flag keywords
│   │   ├── schemas/                   # Pydantic v2 validation & response models
│   │   ├── services/                  # Business logic & algorithms
│   │   │   ├── audit_service.py       # Append-only audit logger
│   │   │   ├── email_service.py       # Outbound SMTP / test mailbox service
│   │   │   ├── password_reset_service.py # Rate-limited token issuance & verification
│   │   │   ├── evidence_service.py    # Segment quality & uncertainty classification
│   │   │   ├── moderation_service.py  # 4-state moderation machine & keyword flags
│   │   │   └── routing_service.py     # Multi-attribute utility ranking & coordinate validation
│   │   ├── cli.py                     # Administrative CLI tool (create-admin, seed)
│   │   └── main.py                    # Lifespan, CORS, error handlers, static mount
│   ├── data/                          # Data store & cache directory
│   │   ├── cache/                     # Cached GraphML street networks & facility JSONs
│   │   └── routing_evaluation_results.json # Empirical benchmark results
│   ├── scripts/                       # Research evaluation & benchmarking scripts
│   │   └── evaluate_routing_methodology.py # Experimental routing evaluation & sensitivity sweeps
│   ├── migrations/                    # Alembic migration scripts
│   │   ├── versions/                  # Schema revisions (add password reset and feedback)
│   │   └── env.py                     # Migration runner with batch SQLite support
│   ├── tests/                         # Pytest automated test suite (111 passing tests across 18 modules)
│   │   ├── test_algorithm_mathematical_evaluation.py # Deterministic hand-calculated graph fixture tests
│   │   ├── test_end_to_end_user_workflows.py # 13-stage comprehensive user journey test
│   │   ├── test_frontend_route_integration.py # Frontend DOM/CSS contract & accessibility tests
│   │   ├── test_routing_integration.py # Multi-preference routing, Yen alternatives & error handling
│   │   ├── test_dijkstra_routing.py   # Multi-attribute Dijkstra & Yen algorithm tests
│   │   └── test_geospatial_foundation.py # OSMnx, network cache, lighting, crime, facilities
│   ├── alembic.ini                    # Alembic configuration
│   ├── requirements.txt               # Backend dependencies (fastapi, osmnx, networkx, geopandas, shapely)
│   ├── .env.example                   # Environment configuration template
│   └── safepath.db                    # Local SQLite database
├── safepath_pro.html                  # Active frontend application
├── styles.css                         # Restrained, responsive Forest Green styling
├── api_service.js                     # Unified API client & data layer
├── app.js                             # Interactive UI controller & Leaflet maps
├── API_CONTRACT.md                    # Detailed REST API specification
├── RESEARCH_METHODOLOGY.md            # Comprehensive Academic Methodology & Evaluation Document
└── README.md                          # Platform documentation
```

### Technology Matrix

- **Backend Framework**: Python 3.12 + [FastAPI](https://fastapi.tiangolo.com/) (v0.115+)
- **Geospatial & Network Graph Stack**:
  - **OSMnx** (v2.1+): OpenStreetMap pedestrian street network retrieval, Overpass filtering, and features
  - **NetworkX** (v3.7+): Directed graph representation, connectivity analysis, and shortest-path topology
  - **GeoPandas** (v1.2+) & **Shapely** (v2.2+): Spatial vector manipulation, centroid matching, and geometry
- **Data Validation & Settings**: [Pydantic v2](https://docs.pydantic.dev/) (`BaseModel`, `Field`, `ConfigDict`)
- **Database & ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with typed `Mapped[...]` attributes
- **Schema Migrations**: [Alembic](https://alembic.sqlalchemy.org/) with batch SQLite support for foreign keys
- **Security & Cryptography**:
  - Passwords: **Argon2id** via `argon2-cffi`
  - Field-Level Encryption: **AES-128 Fernet** via `cryptography`
  - Authentication: **JSON Web Tokens (JWT)** via `pyjwt` with HMAC-SHA256 signatures
  - Reset Tokens: Cryptographically secure 32-byte tokens hashed with **SHA-256** at rest
- **Automated Testing**: [Pytest](https://docs.pytest.org/) + `pytest-asyncio` + Starlette `TestClient` (111 passing tests across 18 modules)
- **Frontend Architecture**: Vanilla HTML5, CSS3, JavaScript (ES6+), [Leaflet.js](https://leafletjs.com/) v1.9.4.

---

## 2. Database Architecture & Schema Design

The backend uses a clean, relational schema designed for strict user isolation (IDOR protection) and auditable governance.

### Entity Relationship Overview

| Model Table             | Purpose                      | Primary Keys & Foreign Keys                         | Key Invariants                                                             |
| :---------------------- | :--------------------------- | :-------------------------------------------------- | :------------------------------------------------------------------------- |
| `users`                 | User accounts & roles        | `id` (UUID str)                                     | Roles: `traveller`, `moderator`, `administrator`. Unique lowercase emails. |
| `password_reset_tokens` | Recovery tokens              | `id` (UUID), `user_id` -> `users.id`                | Single-use (`used` flag), 30m expiry, token hashed with SHA-256 at rest.   |
| `feedback`              | User & support tickets       | `id` (String), `user_id` -> `users.id` (nullable)   | Categories, ratings, status (`new`, `in_review`, `resolved`, `dismissed`). |
| `community_reports`     | Infrastructure reports       | `id` (String), `user_id` -> `users.id` (nullable)   | Moderation states: `pending`, `approved`, `rejected`, `flagged`.           |
| `saved_journeys`        | Saved walking plans          | `id` (UUID), `user_id` -> `users.id`                | Scoped to owning user. Cascades on user deletion.                          |
| `journey_history`       | Completed trips              | `id` (UUID), `user_id` -> `users.id`                | Records arrival confirmation and contacts notified.                        |
| `saved_places`          | Origin/destination shortcuts | `id` (UUID), `user_id` -> `users.id`                | Custom labels (Home, Work, Transit).                                       |
| `trusted_contacts`      | Emergency circle             | `id` (UUID), `user_id` -> `users.id`                | Field-level encrypted `name` and `phone` via AES-128 Fernet.               |
| `journey_shares`        | ETA share dispatch records   | `id` (UUID), `journey_id`, `user_id`                | Tracks intended vs delivered recipients and provider status.               |
| `arrival_confirmations` | Destination pings            | `id` (UUID), `journey_id`, `user_id`                | Delivery confirmation timestamp and provider status.                       |
| `evidence_sources`      | Upstream data registries     | `id` (String)                                       | Quality score, coverage, sync dates, and confidence ratings.               |
| `street_segments`       | Segment-level provenance     | `id` (String), `source_id` -> `evidence_sources.id` | Segment state: `available`, `limited`, `insufficient`, `outdated`.         |
| `audit_logs`            | Append-only governance log   | `id` (UUID), `actor_id`                             | Immutable trail of role changes, identity reveals, moderation decisions.   |
| `system_settings`       | Dynamic thresholds           | `key` (String, PK)                                  | Freshness window (30d), outdated window (90d), auto-flag keywords.         |

---

## 3. How to Run the Application

### 3.1 Prerequisites

- Python 3.10+ (tested on Python 3.12)
- Virtual environment (`venv`)

### 3.2 Backend Setup & Execution

#### Step 1: Initialize Virtual Environment & Install Dependencies

```bash
cd "safe path"
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

#### Step 2: Configure Environment Variables

Copy the template configuration:

```bash
cp backend/.env.example backend/.env
```

Key configuration values in `backend/.env`:

```ini
PROJECT_NAME="SafePath Finder Backend"
ENVIRONMENT="development"
SECRET_KEY="generate-a-secure-random-secret-key"
DATABASE_URL="sqlite:///safepath.db"
FIELD_ENCRYPTION_KEY="REPLACE_WITH_BASE64_FERNET_KEY"
SMTP_HOST=""
CORS_ORIGINS=["http://localhost:8000","http://127.0.0.1:8000","http://localhost:8001","http://127.0.0.1:8001"]
```

#### Step 3: Run Database Migrations

Apply the initial schema migration using Alembic:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/alembic upgrade head
```

#### Step 4: Seed Demonstration Fixtures

Populate the database with the Bengaluru pilot corridor street segments, data sources, and sample reports:

```bash
PYTHONPATH=. ../.venv/bin/python app/cli.py seed
```

#### Step 5: Provision Administrator Account

Create a default administrator account via the administrative CLI:

```bash
PYTHONPATH=. ../.venv/bin/python app/cli.py create-admin --email admin@safepath.org --name "SafePath Administrator" --password "AdminPass123!"
```

#### Step 6: Launch the Backend API Server

Start the Uvicorn server:

```bash
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

The backend API is now running at:

- **Interactive Swagger Docs**: [http://127.0.0.1:8001/api/docs](http://127.0.0.1:8001/api/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8001/api/redoc](http://127.0.0.1:8001/api/redoc)
- **Health Check**: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

---

### 3.3 Running the Frontend & Live Integration

SafePath can be accessed in two ways:

#### Option A: Unified FastAPI Server (Recommended)

FastAPI mounts the frontend static files directly at `/`. When running Uvicorn on port `8001` or `8000`, open:

- [http://127.0.0.1:8001/safepath_pro.html](http://127.0.0.1:8001/safepath_pro.html)

#### Option B: Dedicated Frontend Server with Cross-Origin API

If running a separate static server on port 8000:

```bash
cd "safe path"
python3 -m http.server 8000
```

Open [http://localhost:8000/safepath_pro.html](http://localhost:8000/safepath_pro.html). In the **Admin Console** -> **System Settings**, configure the API Base URL to `http://127.0.0.1:8001/api/v1` or toggle live mode via `SafePathApi.setMode('live')`.

---

## 4. Geospatial Evidence Processing & Database Integration

SafePath Finder incorporates a scientific, testable evidence pipeline that transforms multi-source geospatial data into street-segment-level evidence indicators.

```
                    Raw Geospatial Sources
       ┌─────────────────┬──────────────────┬─────────────────┐
       │ OpenStreetMap   │ Documented Crime │ Civic POIs      │ Community Reports
       │ Pedestrian Ways │ Validated CSV    │ Police & Health │ (DB Submissions)
       └────────┬────────┴────────┬─────────┴────────┬────────┴────────┬────────┘
                │                 │                  │                 │
                ▼                 │                  │                 │
      ┌──────────────────┐        │                  │                 │
      │ Pedestrian Graph │        │                  │                 │
      │ (UTM Projection) │        │                  │                 │
      └─────────┬────────┘        │                  │                 │
                │                 │                  │                 │
                ▼                 ▼                  ▼                 ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │                     Spatial Matching & Processing                      │
     │  - Shapely STRtree Point-to-Edge Snapping (tolerance <= 30m)           │
     │  - Lighting Epistemology (lit, unlit, conflicting, unmapped)           │
     │  - Pedestrian Network Shortest Path Dijkstra (1.2 m/s walking speed)   │
     │  - Crime PII Rejection, Deduplication & Length Normalization           │
     │  - Community Report Taxonomy Mapping & Moderation vs Ground Truth      │
     └───────────────────────────────────┬────────────────────────────────────┘
                                         │
                                         ▼
                     Standardized Evidence Persistence
                ┌─────────────────────────────────────────┐
                │ StreetSegment                           │
                │  - edge_u, edge_v, length_meters        │
                │  - lit_status (lit|unlit|conflicting|   │
                │                unmapped)                │
                │  - nearest_police_distance_meters       │
                │  - nearest_hospital_distance_meters     │
                │  - crime_rate_per_km, crime_count       │
                │  - community_reports_count              │
                ├─────────────────────────────────────────┤
                │ EvidenceObservation                     │
                │  - Atomic matched evidence point        │
                │  - Category, source, observed_at        │
                │  - Verification & data_state flags      │
                │  - STRICTLY ZERO REPORTER PII           │
                └─────────────────────────────────────────┘
```

### 4.1 The Four Evidence Streams

#### 1. Historical Crime Incidents

- **Input Format**: Validated CSV schema (`incident_id,latitude,longitude,category,timestamp,severity,spatial_precision,source`).
- **Privacy Enforcement**: Datasets containing prohibited personal identifying information (`name`, `victim`, `suspect`, `phone`, `email`, `address`, `national_id`) are **strictly rejected with HTTP 422**.
- **Deduplication**: Rows with duplicate IDs or identical `(lat, lon, date, category)` fingerprints are flagged and deduplicated.
- **Severity Taxonomy**:
  - _High_: `violent_crime`, `assault`, `robbery`, `sexual_assault`, `homicide`, `weapon`, `felony`.
  - _Medium_: `theft`, `burglary`, `larceny`, `harassment`, `stalking`, `misdemeanor`.
  - _Low_: `vandalism`, `public_intoxication`, `trespassing`, `disorderly_conduct`, `minor_infraction`.
  - _Unclassified_: Sources lacking reliable severity are marked `severity = None` with explicit limitation documentation.
- **Exposure Normalization**: Incidents are filtered to the stated historical window (default 365 days) and normalized by segment length:
  $$\text{crime\_rate\_per\_km} = \frac{\text{incident\_count}}{\max(\text{length\_meters} / 1000, 0.05)}$$
- **Scientific Guardrail**: Raw counts and rates are documented as **historical evidence indicators**, NEVER converted into personal probabilities of victimization.

#### 2. Explicit Street Lighting Information

- **Epistemological Distinction**:
  - `lit`: Explicit affirmative tag (`lit=yes`, `lit=24/7`, `lit=dusk-dawn`).
  - `unlit`: Explicit negative tag (`lit=no`, `lit=disused`).
  - `conflicting`: Tagged `lit=yes` but approved community reports document broken luminaires or non-functioning lamps within 90 days.
  - `unmapped`: Absence of lighting tags on OpenStreetMap edges represents a survey gap, **NOT physical darkness**. Missing data is preserved as `missing`/`unmapped` uncertainty rather than assuming dark conditions.
- **Mapped Streetlamps vs Way Attributes**: Mapped point assets (`highway=street_lamp`) are recorded as localized infrastructure, but do **not** imply that an entire street segment is fully illuminated.
- **Operational Reality**: Mapped lights are not assumed to be functioning or turned on during nighttime journeys.

#### 3. Civic Assistance Facilities (Police & Hospitals)

- **Distinct Facility Models**: Police stations and hospitals/emergency clinics are retrieved, mapped, and queried separately.
- **Pedestrian Network Routing**: Walking access is calculated using multi-source Dijkstra shortest-path algorithms on the pedestrian network graph assuming a nominal pedestrian speed of $1.2 \text{ m/s}$ ($72 \text{ m/min}$).
- **Explicit Distance Labeling**:
  - Reachable network nodes: labeled `distance_type: "network_walking"` (`is_straight_line = false`).
  - Disconnected subgraph nodes: fall back to Euclidean straight-line distance, labeled `distance_type: "euclidean_straight_line"` (`is_straight_line = true`) with an explicit disclaimer. Straight-line distance is **never substituted without transparent labeling**.
- **Crucial Separation**: Proximity to a police station or hospital is an assistance accessibility metric, **NOT proof that a street has low crime risk**.
- **Availability Guardrail**: Facility operating hours and staffing status are not inferred unless verified.

#### 4. Recent Community Feedback & Reports

- **Taxonomy Mapping**:
  - Lighting concerns $\rightarrow$ Category: `lighting`, Subcategory: `lighting_concern`
  - Harassment / threatening behavior $\rightarrow$ Category: `community_hazard`, Subcategory: `harassment`
  - Reported crime / theft $\rightarrow$ Category: `safety_incident`, Subcategory: `reported_incident`
  - Physical obstruction / broken path $\rightarrow$ Category: `community_hazard`, Subcategory: `access_obstruction`
  - General observations $\rightarrow$ Category: `civic_observation`, Subcategory: `general_observation`
- **Moderation vs Ground-Truth Certainty**: Administrative approval confirms policy adherence and suitability for routing display, **not absolute factual certainty**. Approved reports have `confidence = "moderate"`; unverified reports have `confidence = "low"`.
- **Deduplication & Staleness**:
  - Reports within 30m and 24 hours in the same category are clustered as corroborations.
  - Reports older than 180 days are classified as `data_state = "stale"`.
  - A single unverified report never marks an entire street as dangerous.
- **Privacy Protection**: Reporter personal details (`reporter_name`, `user_id`, `email`, `phone`, `ip_address`) are **completely stripped** from all evidence exports, ORM observation models, and public API responses.

---

### 4.2 Evidence Quality States

Every evidence observation and street segment explicitly tracks its epistemological quality state:

- `present`: Documented, verified data observed within the active freshness window.
- `missing`: No data available for this segment/attribute (must never be converted to zero risk or safe).
- `stale`: Observations exist but exceed freshness threshold (>180 days).
- `conflicting`: Opposing observations (e.g. `lit=yes` way tag vs recent broken lighting community report).
- `insufficient`: Low sample size or observational confidence below conclusive threshold.

---

### 4.3 Database Model & Migration Changes

Alembic migration revision `de47e3e082dd` (`add evidence observations and segment attributes`):

1. **Extended `StreetSegment`** table:
   - `edge_u` (Integer), `edge_v` (Integer), `edge_key` (Integer)
   - `length_meters` (Float)
   - `lit_status` (String: `lit`, `unlit`, `conflicting`, `unmapped`, default `'unmapped'`)
   - `nearest_police_distance_meters` (Float), `nearest_police_walking_minutes` (Float)
   - `nearest_hospital_distance_meters` (Float), `nearest_hospital_walking_minutes` (Float)
   - `crime_count` (Integer, default 0), `crime_rate_per_km` (Float, default 0.0)
   - `community_reports_count` (Integer, default 0)
   - `evidence_summary` (JSON)
2. **New `EvidenceObservation`** table:
   - Atomic matched observation records (`id`, `source_id`, `source_type`, `category`, `subcategory`, `latitude`, `longitude`, `geometry`, `segment_id`, `edge_u`, `edge_v`, `edge_key`, `match_distance_meters`, `match_method`, `match_status`, `observed_at`, `ingested_at`, `source_attribution`, `verification_status`, `severity`, `confidence`, `data_state`, `provenance`, `limitations`, `attributes`).
   - Strictly devoid of any reporter personal identification fields.
   - Indexed across `category`, `data_state`, `source_type`, `match_status`, and `observed_at`.

---

### 4.4 Study Area Coverage Summary & Remaining Data Gaps

Audited metrics for the configured Bengaluru Pedestrian Research Corridor (`[77.5800, 12.9250, 77.5950, 12.9400]`):

- **Pedestrian Network**: 482 edges indexed via Shapely STRtree in projected UTM Zone 43N (EPSG:32643).
- **Lighting Coverage**:
  - Explicitly Lit: ~14.1%
  - Explicitly Unlit: ~2.9%
  - Conflicting: ~0.4%
  - **Unmapped / Unknown**: ~82.6% (preserved as informational gap, not assumed dark).
- **Assistance Facilities**:
  - Police Stations: 4 POIs mapped; 78.8% of pedestrian edges within 15-minute walking distance.
  - Hospitals / Healthcare: 5 POIs mapped; 85.5% of pedestrian edges within 20-minute walking distance.
- **Remaining Data Gaps**:
  1. _Lighting Tag Incompleteness_: 82.6% of street segments lack explicit OpenStreetMap lighting tags.
  2. _Crime Data Spatial Aggregation_: Indian police records are published as district-level annual aggregates rather than open point-level GPS data. SafePath ingests verified CSV datasets when supplied, but strictly refuses to fabricate synthetic incidents.
  3. _Facility Operating Hours_: Real-time staffing and night-shift emergency availability are unverified in OpenStreetMap POIs.

---

## 5. Walking Routing & Route-Ranking Engine

SafePath Finder implements genuine, deterministic pedestrian routing based on graph theory and multi-attribute utility analysis. It explicitly avoids A\*, K-means clustering, speculative crowd estimation, and generative AI hallucinations.

### 5.1 Three Primary Route Preferences (Dijkstra's Algorithm)

The pedestrian network is modeled as an OSMnx directed multigraph (`nx.MultiDiGraph`) with real street geometry vertices, edge lengths ($D_e$ in meters), and estimated pedestrian traversal times:
$$T_e = \frac{D_e}{V_{\text{walk}}}$$
where $V_{\text{walk}} = 1.2 \text{ m/s}$ ($72 \text{ m/min}$, configurable via `WALKING_SPEED_MPS`). Traversal times $T_e$ are guaranteed finite and non-negative.

Dijkstra's algorithm is run independently for each preference using the generalized edge cost:
$$\text{Cost}_e = T_e \times (1 + \lambda \times R_{\text{effective}_e})$$

1. **Fastest Route** ($\lambda = 0$):
   - Minimizes pure walking duration: $\text{Total Time} = \sum T_e$.
   - Baseline shortest duration. Does not divert to avoid unlit or unmapped streets.
2. **Balanced Route** ($\lambda = \lambda_{\text{balanced}} > 0$, default `1.0`):
   - Balances walking duration with verified lighting, assistance access, and reported safety.
   - Accepts moderate detours along active commercial avenues.
3. **Safety-Prioritized Route** ($\lambda = \lambda_{\text{safety}} > \lambda_{\text{balanced}}$, default `3.0`):
   - High risk penalty that strongly diverts around dark, conflicting, or higher-crime street segments.
   - Labeled honestly as **“Safety-prioritized”**—never “Guaranteed safe”. Shows users transparent trade-offs (e.g. _“Adds ~5 min walking time to reduce effective risk indicator by 0.15”_).
   - Constrained by a maximum detour ratio (default $1.6\times$ of fastest duration, configurable via `ROUTING_MAX_DETOUR_RATIO`).

---

### 5.2 Multi-Criteria Segment-Risk Model & Missing-Data Handling

Each segment evaluates four normalized risk indicators ($I_i \in [0, 1]$, where higher indicates greater concern) and indicator coverage qualities ($Q_i \in [0, 1]$):

1. **Crime-Related Indicator** ($I_{\text{crime}}, Q_{\text{crime}}$):
   - Based on documented incident data normalized by segment length (incidents/km), preventing bias against longer streets.
   - Does **not** represent personal victimization probability. Unmapped crime data defaults to $Q=0$.
2. **Street Lighting Indicator** ($I_{\text{lighting}}, Q_{\text{lighting}}$):
   - Explicitly lit (`lit=yes` / `lit=lit`): $I = 0.10, Q = 1.0$.
   - Explicitly unlit (`lit=no` / `lit=unlit`): $I = 0.90, Q = 1.0$.
   - Conflicting evidence: $I = 0.65, Q = 0.80$.
   - **Unmapped / Unknown**: $I = R_{\text{unknown}}, Q = 0.0$. Never assumes dark merely because data is absent!
3. **Community Feedback Indicator** ($I_{\text{community}}, Q_{\text{community}}$):
   - Moderated hazard and harassment reports.
   - Surveyed corridors with zero reports yield $Q = 0.70, I = 0.05$; unmapped corridors yield $Q = 0.0$.
4. **Assistance Access Indicator** ($I_{\text{assistance}}, Q_{\text{assistance}}$):
   - True pedestrian network walking time to nearest police station and hospital (kept distinct in data).
   - Proximity is an accessibility factor, not proof that a street is safe.

#### Epistemological Missing-Data Formula:

$$Q = \sum w_i Q_i \quad \left(\sum w_i = 1.0\right)$$
$$R_{\text{effective}} = Q \times R_{\text{observed}} + (1 - Q) \times R_{\text{unknown}}$$

- Missing evidence is **never encoded as zero risk**.
- $R_{\text{unknown}}$ is a configurable prior (default `0.50`, configurable via `ROUTING_DEFAULT_R_UNKNOWN`) clearly labeled as a modeling assumption.
- If route evidence coverage $Q < 0.30$ (`ROUTING_MIN_COVERAGE_THRESHOLD`), the route is explicitly flagged with `hasInsufficientEvidence: true`.

---

### 5.3 Additional Route Alternatives (Yen's K-Shortest Paths Algorithm)

Additional distinct alternatives are generated using Yen's loopless paths algorithm (`nx.shortest_simple_paths`) on a simplified directed graph collapsed by minimum edge cost:

- MultiDiGraph parallel edges are mapped back to their exact keys, geometries, and attributes.
- Duplicate and near-duplicate paths are filtered using Jaccard edge overlap:
  $$\text{Overlap}(P_1, P_2) = \frac{|E_1 \cap E_2|}{|E_1 \cup E_2|}$$
  Candidates with $\text{Overlap} \ge 0.80$ (`ROUTING_ALTERNATIVE_OVERLAP_THRESHOLD`) are rejected.
- Paths are strictly loopless, connected, and returned in non-decreasing cost order. If fewer valid alternatives exist, fewer are returned.

---

## 6. Automated Testing Suite & Empirical Benchmarks

The project includes **123 passing automated tests** across 19 test modules:

```bash
cd "safe path/backend"
PYTHONPATH=. ../.venv/bin/pytest -v
```

### Complete Test Suite Execution (123 passed)

```
tests/test_algorithm_mathematical_evaluation.py .....                    [  4%]
tests/test_auth.py ............                                          [ 13%]
tests/test_contacts_sharing.py ...                                       [ 16%]
tests/test_dijkstra_routing.py .........                                 [ 23%]
tests/test_end_to_end_user_workflows.py .                                [ 24%]
tests/test_evidence_pipeline.py ................                         [ 37%]
tests/test_feedback.py .....                                             [ 41%]
tests/test_frontend_route_integration.py ......                          [ 46%]
tests/test_geocoding.py ...........                                      [ 55%]
tests/test_geospatial_foundation.py ...............                      [ 67%]
tests/test_journeys.py ...                                               [ 69%]
tests/test_migrations.py .                                               [ 70%]
tests/test_moderation_admin.py .........                                 [ 78%]
tests/test_navigation_contract.py ...                                    [ 80%]
tests/test_password_reset_advanced.py ...                                [ 82%]
tests/test_privacy_hardening.py .....                                    [ 86%]
tests/test_reports.py ......                                             [ 91%]
tests/test_routing_evidence.py ....                                      [ 95%]
tests/test_routing_integration.py ......                                 [100%]
======================== 123 passed, 1 warning in 9.67s ========================
```

### Key Test Suites Breakdown

#### 1. Location Search, Geocoding & Boundary Separation (`tests/test_geocoding.py`)

1. `test_case_insensitive_searches`: Verifies case-insensitivity across `"electronic city"`, `"Electronic City"`, `"ELECTRONIC CITY"`, and mixed case with request cache deduplication.
2. `test_partial_place_name_search`: Partial place names (`"jayanag"`, `"lalba"`, `"cubb"`) return relevant suggestions.
3. `test_street_addresses_and_landmarks_with_locality_city_region`: Suggestion display names and structured address objects include locality, city, and state components.
4. `test_multiple_similarly_named_places`: Returns multiple distinct suggestions for broader neighborhood names (e.g. Jayanagar).
5. `test_direct_coordinate_query_parsing`: Direct coordinate queries (`"12.9257, 77.5833"`) are automatically identified as coordinate matches with in-bounds evaluation.
6. `test_separation_of_geocoding_from_routing_coverage`: Proves that Electronic City is successfully geocoded to its true coordinates `(12.8436, 77.6687)` and marked `inStudyArea=False`, and submitting it to the routing engine cleanly raises HTTP 400 `OutOfCoverageError` rather than claiming the location does not exist.
7. `test_selected_coordinates_passed_to_route_endpoint`: Verifies that selected autocomplete coordinates are transmitted and directly consumed by the Dijkstra router.
8. `test_unknown_location_returns_controlled_error`: Completely unresolvable places cleanly return HTTP 422 with informative user feedback.
9. `test_invalid_coordinate_ranges`: Out-of-range coordinates (> 90 lat) return HTTP 422.
10. `test_geocoding_provider_failure_handling`: Upstream timeouts/HTTP 503 cleanly return HTTP 503 with user guidance to enter coordinates directly.
11. `test_geocoding_zero_pii_and_security`: Verifies that no API keys, passwords, or personal credentials are leaked.

#### 2. Mathematical Algorithm Correctness (`tests/test_algorithm_mathematical_evaluation.py`)

Deterministic tests executed against hand-calculated small graph fixtures with independently derived analytical solutions:

1. `test_hand_calculated_fixture_cost_minimization`: Proves Fastest strictly minimizes traversal duration ($T$), Balanced minimizes $T(1 + \lambda_{\text{balanced}} R)$, and Safety-prioritized minimizes $T(1 + \lambda_{\text{safety}} R)$ across 3 synthetic corridors (Short Dark Alley, Medium Mixed Road, Long Lit Boulevard).
2. `test_separation_of_coverage_from_risk`: Verifies that missing data ($Q=0$) produces $R_{\text{effective}} = R_{\text{unknown}}$, and varying coverage $Q$ on an uncorroborated street never produces zero risk.
3. `test_risk_weight_lambda_transition_point`: Evaluates the analytical indifference point $\lambda^* = \frac{T_2 - T_1}{T_1 R_1 - T_2 R_2} = 1.0$, verifying that the router selects the shortcut for $\lambda < 1.0$ and the lit detour for $\lambda > 1.0$.
4. `test_disconnected_network_produces_controlled_error`: Asserts that disconnected network components raise `DisconnectedNetworkError` without unhandled exceptions or crash.
5. `test_loopless_yen_paths_cost_ordering`: Verifies that Yen's algorithm generates loopless paths in strictly non-decreasing cost order.

#### 3. End-to-End User Lifecycle & Security Workflows (`tests/test_end_to_end_user_workflows.py`)

Executes all 13 core user and administrative journeys in a single continuous deterministic workflow:

1. User registration with Argon2id password hashing.
2. User authentication and JWT access token issuance.
3. Walking route planning between valid study area coordinates.
4. Fastest route preference validation.
5. Balanced route preference with environmental impedance.
6. Safety-prioritized route preference with risk-aversion penalty.
7. Genuine alternative paths inspection via Yen's algorithm.
8. Street segment evidence and uncertainty audit.
9. Community feedback submission and database persistence.
10. Administrative moderation inbox inspection and status transitions.
11. Admin audit logging and dynamic setting management.
12. Single-use cryptographically secure password reset token issuance and redemption.
13. AES-128 Fernet encrypted trusted contact creation, journey ETA sharing, and logout token revocation.

#### 4. Routing Integration & Coordinate Boundary Tests (`tests/test_routing_integration.py`)

1. Multi-preference comparison endpoint (`POST /api/v1/routes/compare`).
2. Verification of distinct Yen alternatives ordered by cost.
3. Strict rejection of unresolvable locations (HTTP 422 `InvalidCoordinateError` / `LocationNotFoundError`).
4. Strict rejection of coordinates outside the pilot study area (HTTP 400 `OutOfCoverageError`).
5. Detection and user-facing explanation of routes identical to the fastest baseline.
6. Absolute exclusion of personally identifiable information (PII) from route geometries and segment properties.

#### 6. Phase 3 Explainable Map Experience & Journey Protection (`tests/test_phase3_explainable_experience.py`)

1. `test_map_layers_bundle_structure_and_legends`: Validates `GET /api/v1/evidence/map-layers` returning all 7 geospatial feature collections (facilities, landmarks, dogs, reports, lighting, pedestrian infra, crime observations) alongside 4 structured legend categories (Mapped Data, Community Reports, Inferred Values, Unknown Info) and safety disclaimers.
2. `test_street_segment_inspection_multidimensional_evidence`: Validates Dijkstra router segment payloads delivering all 13 distinct physical and epistemological dimensions (street name, length, walking time, crime evidence, lighting status, dog encounters, pedestrian infrastructure, open establishments, police/transit proximity, community reports, coverage $Q(e)$, uncertainty prior $R_{\text{unknown}}$, unmapped status) without collapsing them into an unexplained synthetic score.
3. `test_departure_period_routing_behavior_and_limitations`: Validates dynamic time-of-day penalty adaptation across Daytime, Evening, and Night, ensuring daylight reduces darkness sensitivity while evening/night heavily penalizes unlit corridors without asserting live bulb status.
4. `test_independent_report_confirmations_and_outdated_flags`: Validates `POST /reports/{id}/confirm` and `POST /reports/{id}/outdated` tracking separate counters, preventing author self-endorsement, allowing vote retractions, and maintaining idempotency.
5. `test_user_report_status_and_mine_endpoint`: Validates `GET /reports/mine` returning traveler report histories with moderation lifecycle tracking.
6. `test_trusted_contact_journey_session_lifecycle`: Validates complete lifecycle of `JourneySession` from voluntary consent creation, live ETA countdown, 5-minute reminder simulation, safe arrival check-in, to cancellation.
7. `test_public_journey_share_token_access_and_zero_pii_leak`: Validates `GET /journey-shares/public/{token}` for non-authenticated contacts, strictly proving zero leakage of traveler user ID, email, phone, or trusted contact identities.
8. `test_peer_reassurance_boundaries_and_no_emergency_claims`: Asserts explicit disclaimers across all journey endpoints confirming SafePath does not dispatch emergency services and missed check-ins do not prove an emergency.

---

### Complete Pytest Test Suite (210 Passing Tests)

The full test suite covers 210 automated tests across 27 modules:

```bash
cd "safe path/backend"
PYTHONPATH=. ../.venv/bin/pytest tests/ -q
# Output: 210 passed in ~73s
```

### Running the Research Methodology Evaluation Script

To replicate the empirical route benchmarks and sensitivity sweeps across the pilot study area:

```bash
cd "safe path/backend"
PYTHONPATH=. ../.venv/bin/python scripts/evaluate_routing_methodology.py
```

Benchmark outputs are persisted to [`backend/data/routing_evaluation_results.json`](file:///home/kevinluke/safe%20path/backend/data/routing_evaluation_results.json) and fully documented in [`RESEARCH_METHODOLOGY.md`](file:///home/kevinluke/safe%20path/RESEARCH_METHODOLOGY.md).

---

## 7. Known Data Gaps & Model Limitations

1. **Incomplete Streetlight Auditing**: OpenStreetMap tag coverage in Indian urban centers currently hovers around 15–20%. Segments lacking `lit` tags are preserved as unmapped uncertainty ($Q=0, R=0.50$).
2. **Uneven Community Reporting**: High-density residential zones report more frequently than commercial arterial roads. Lack of reports does not guarantee safety.
3. **Emergency Facility Availability**: Proximity to hospitals and police stations reflects walking network access, not confirmed immediate availability, open gates, or bed capacity.
4. **Research Prototype Status**: Model weights ($\lambda_{\text{balanced}}=1.0, \lambda_{\text{safety}}=3.0, R_{\text{unknown}}=0.50$) are initial provisional research parameters, not scientifically validated clinical or epidemiological thresholds.

---

## 8. Running the Application

### 1. Start the FastAPI Backend

```bash
cd "safe path/backend"
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 2. Start the Frontend

```bash
cd "safe path"
python3 -m http.server 8000
```

Open [http://localhost:8000/safepath_pro.html](http://localhost:8000/safepath_pro.html).

---

## 9. Research Methodology Documentation & Publications

For the complete academic specification, including mathematical formulations of the multi-attribute edge impedance, the epistemological missing-data policy, experimental design, and empirical route benchmark tables across the Bengaluru Pilot Corridor, refer to:

- [`RESEARCH_METHODOLOGY.md`](RESEARCH_METHODOLOGY.md) — _SafePath Finder: Research Methodology, Routing Engine Evaluation, and Epistemological Uncertainty Model_
- [`API_CONTRACT.md`](API_CONTRACT.md) — _Complete REST API Contract and Parameter Schemas_

---

## 10. License & Research Attribution

Developed for women's safety, accessible mobility, and urban navigation research. Distributed under the MIT License.
