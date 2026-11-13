# SafePath Finder — REST API Specification & Architecture Contract

**Base URL**: `/api/v1`  
**Current Version**: `v1.0.0`  
**Protocol**: HTTPS (Production) / HTTP (Local Development)  
**Standard Port**: `8001` (Backend API) / `8000` (Frontend or Combined Server)

---

## 1. Architectural & Security Principles

1. **Server-Side Authorization**: Frontend role checks and visual indicators are strictly presentation layer. The backend validates and enforces authentication and role-based permissions (`traveller`, `moderator`, `administrator`) on every privileged endpoint.
2. **Data Minimization & Anti-Doxxing**: The reporting surface strictly disallows personally identifiable information (PII) including individual names, photos containing recognizable persons, and exact residential addresses.
3. **Evidence vs Safety Invariant**: **Missing data must NEVER be encoded as low risk**. Absence of recorded incidents or lack of lighting audit data must result in an explicit `insufficient` or `limited` status with high uncertainty indicators rather than an optimistic safety score.
4. **Transparent Routing Reasoning**: SafePath explicitly does not compute black-box safety scores. Routing recommendations disclose exact trade-offs (e.g., additional minutes vs verified lighting coverage).
5. **Telephony & Dispatch Honesty**: SMS, WhatsApp, and emergency dispatch alerts require real external provider integration. The backend and client explicitly report delivery status (`pending_provider_integration`, `delivered`, `failed`) and never falsely imply verified delivery.
6. **IDOR & Data Isolation**: All queries for private user resources (saved journeys, places, contacts, reports) strictly enforce `user_id == current_user.id` at the database level.
7. **Audit Trail**: Privileged administrative and moderation actions are logged in an append-only audit table recording actor, action, entity, timestamp, and client metadata.

---

## 2. Authentication & Session Management

Protected endpoints require a standard HTTP Authorization header:
```http
Authorization: Bearer <signed_jwt_access_token>
```

Tokens are signed using HS256 (or RS256 in production) with a 24-hour expiration window.

### Standard Response Envelopes
List endpoints follow a standardized pagination envelope:
```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 20
}
```

Validation errors follow RFC 7807 structured error format:
```json
{
  "status": 422,
  "message": "Input validation failed. Please check the submitted fields.",
  "errors": [
    {
      "field": "body -> email",
      "message": "value is not a valid email address",
      "type": "value_error"
    }
  ]
}
```

---

## 3. Endpoints Specification

### 3.1 Identity & Authentication

#### `POST /auth/register`
Creates a new traveller account with Argon2id password hashing.
- **Access**: Public
- **Request Body**:
  ```json
  {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Responses**:
  - `201 Created`:
    ```json
    {
      "accessToken": "eyJhbGciOi...",
      "tokenType": "bearer",
      "user": {
        "id": "usr-uuid",
        "email": "jane@example.com",
        "name": "Jane Doe",
        "role": "traveller",
        "status": "active",
        "created_at": "2026-10-27T14:00:00Z"
      }
    }
    ```
  - `400 Bad Request`: Email already registered.
  - `422 Unprocessable Entity`: Validation failure (short password, invalid email).

#### `POST /auth/login`
Authenticates a user and issues a signed JWT.
- **Access**: Public
- **Request Body**:
  ```json
  {
    "email": "jane@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Responses**:
  - `200 OK`: Returns token and user object.
  - `401 Unauthorized`: Invalid credentials.

#### `POST /auth/password-reset/request`
Requests a password recovery link. **Security Rule**: Always returns 202 Accepted regardless of whether the email exists, preventing account enumeration.
- **Access**: Public
- **Request Body**:
  ```json
  {
    "email": "jane@example.com"
  }
  ```
- **Responses**:
  - `202 Accepted`:
    ```json
    {
      "status": "accepted",
      "message": "If this email is registered in our database, recovery instructions have been dispatched."
    }
    ```

#### `POST /auth/password-reset/confirm`
Completes password reset using a cryptographically secure token.
- **Access**: Public
- **Request Body**:
  ```json
  {
    "token": "reset-token-str",
    "password": "NewSecurePassword123!"
  }
  ```
- **Responses**:
  - `200 OK`: Password updated successfully.
  - `400 Bad Request`: Token expired or invalid.

#### `POST /auth/logout`
Terminates user session on client and server.
- **Access**: Public / Authenticated
- **Responses**:
  - `200 OK`: `{"status": "ok", "message": "Successfully logged out."}`

#### `GET /me`
Returns profile and permissions of the currently authenticated user.
- **Access**: Authenticated (`Bearer`)
- **Responses**:
  - `200 OK`: Current User object.
  - `401 Unauthorized`: Missing or expired token.

---

### 3.2 Journeys, Routing & Evidence

#### `GET /study-area`
Returns the active research study area configuration, boundary limits, and slug identifier.
- **Access**: Public
- **Response `200 OK`**:
  ```json
  {
    "name": "Bengaluru Pilot Corridor",
    "placeName": null,
    "description": "Active research corridor for SafePath Finder",
    "bbox": {
      "south": 12.9200,
      "west": 77.5700,
      "north": 12.9850,
      "east": 77.6200
    },
    "slug": "bengaluru_pilot_corridor_12p9200_77p5700_12p9850_77p6200"
  }
  ```

#### `GET /study-area/audit`
Executes an audit of real evidence sources accessible to the routing engine: pedestrian street network cache, lighting survey coverage, civic facilities (police and healthcare), crime dataset readiness, and community reports.
- **Access**: Public
- **Response `200 OK`**:
  ```json
  {
    "studyArea": { "name": "Bengaluru Pilot Corridor", ... },
    "network": { "status": "cached", "cachePath": "..." },
    "lighting": { "dataState": "limited", "coveragePercentage": 0.0, "caveat": "..." },
    "facilities": { "policeCount": 25, "hospitalCount": 18, "sources": [...] },
    "crime": { "isLoaded": false, "recordCount": 0, "limitations": [...] },
    "communityReports": { "totalReportsCount": 4, "approvedReportsCount": 2, ... }
  }
  ```

#### `GET /geocoding/search`
Searches for real places, street addresses, landmarks, or coordinates via forward geocoding. Returns structured suggestions with locality, city, region, coordinates, and explicit annotation of whether the location falls within the active pedestrian routing network boundary (`inStudyArea`).

- **Access**: Public
- **Query Parameters**:
  - `q` (required, min 2 chars): Search string (e.g. `"electronic city"`, `"Electronic City"`, `"MG Road"`, `"12.9257, 77.5833"`). Case-insensitive.
  - `limit` (optional, default `5`, max `10`): Maximum suggestions to return.
  - `near_study_area` (optional, default `true`): Biases results toward research study area region while permitting broader searches.
- **Responses**:
  - `200 OK`: Successful search. Returns list of suggestions with study area boundary distance.
  - `503 Service Unavailable`: Upstream geocoding provider timed out, rate-limited, or offline.
- **Example Response `200 OK`**:
  ```json
  {
    "query": "electronic city",
    "provider": "nominatim",
    "count": 2,
    "results": [
      {
        "id": "local_electronic_city",
        "name": "Electronic City",
        "displayName": "Electronic City, Bengaluru, Bangalore South, Bengaluru Urban, Karnataka, 560100, India",
        "latitude": 12.8436,
        "longitude": 77.6687,
        "type": "suburb",
        "address": {
          "suburb": "Electronic City",
          "city": "Bengaluru",
          "state": "Karnataka",
          "postcode": "560100",
          "country": "India"
        },
        "inStudyArea": false,
        "studyAreaDistanceMeters": 10001.8,
        "importance": 0.95,
        "boundingBox": null
      }
    ],
    "studyArea": {
      "name": "Bengaluru Pilot Corridor",
      "bbox": { "south": 12.9200, "west": 77.5700, "north": 12.9850, "east": 77.6200 }
    }
  }
  ```

#### `POST /routes/compare`
Compares walking-route alternatives using transparent multi-attribute utility ranking and explainable trade-offs. Computes primary routes via separate Dijkstra runs on a directed weighted pedestrian network, plus distinct loopless alternatives via Yen's K-shortest paths algorithm with length-weighted spatial overlap filtering ($\le 0.75$). Validates origin and destination coordinates against the active study area boundary.

- **Routing Model Version**: `2.0.0`
- **Generalized Edge Cost**:
  $$\text{Cost}(e) = T(e) \times (1 + \lambda \times R_{\text{effective}}(e))$$
  - **Fastest Route**: $\text{Cost}_{\text{fastest}}(e) = T(e)$ (strictly walking time $\sum T(e)$ based on physical length and $1.2\text{ m/s}$ walking speed, invariant to departure time).
  - **Balanced Route**: $\text{Cost}_{\text{balanced}}(e) = T(e) \times (1 + \lambda_{\text{balanced}} \times R_{\text{effective}}(e))$, default $\lambda_{\text{balanced}} = 1.0$.
  - **Safety-prioritized Route**: $\text{Cost}_{\text{safety}}(e) = T(e) \times (1 + \lambda_{\text{safety}} \times R_{\text{effective}}(e))$, default $\lambda_{\text{safety}} = 3.0$.
  - Invariant: $\lambda_{\text{safety}} > \lambda_{\text{balanced}} \ge 0$.
- **Adverse Risk Model ($R_{\text{observed}}$)**:
  $$R_{\text{observed}}(e) = w_c C(e) + w_l L(e) + w_d D(e) + w_f F(e) + w_p P(e) + w_a A(e)$$
  - Normalised Model Weights (v2.0.0): $w_c = 0.25, w_l = 0.25, w_d = 0.15, w_f = 0.15, w_p = 0.15, w_a = 0.05$. Sum $= 1.00$.
  - $C(e)$: Historical crime-related evidence.
  - $L(e)$: Poor-lighting indicator (diurnally modulated: 0.10 daytime, 0.60 evening, 1.00 night).
  - $D(e)$: Dog-encounter risk indicator (ordinary calm sightings informational, aggressive barking/bites penalized).
  - $F(e)$: Negative community feedback indicator.
  - $P(e)$: Pedestrian infrastructure deficiency indicator (missing sidewalks, high crossing difficulty, active obstructions).
  - $A(e)$: Assistance facility isolation penalty (non-negative distance penalty; assistance access is never treated as proof of low crime).
- **Evidence Coverage & Effective Risk**:
  $$Q(e) = \frac{\sum w_i q_i(e)}{\sum w_i}, \quad R_{\text{effective}}(e) = Q(e) R_{\text{observed}}(e) + (1 - Q(e)) R_{\text{unknown}}$$
  Configured prior $R_{\text{unknown}} = 0.50$. Missing evidence is never encoded as zero risk.
- **Constraints**: Confirmed pedestrian restrictions (`foot=no`, `access=private`, `motorway`) are assigned cost $\infty$. When `stepFree=true`, pedestrian steps and stairs are assigned cost $\infty$.

- **Access**: Public
- **Request Body**:
  ```json
  {
    "origin": "12.9257, 77.5833",
    "destination": "12.9501, 77.5847",
    "walkingMode": "pedestrian",
    "departurePeriod": "night",
    "stepFree": false,
    "originCoordinates": [12.9257, 77.5833],
    "destinationCoordinates": [12.9501, 77.5847],
    "preferences": {
      "preferLighting": true,
      "avoidUnknown": true,
      "includeAlternatives": true,
      "maxAlternatives": 2
    }
  }
  ```
  - `departurePeriod` *(optional, string)*: Intended departure period (`"daytime"`, `"evening"`, `"night"`). Default `"daytime"`.
  - `stepFree` *(optional, boolean)*: Require step-free pedestrian path excluding steps/stairs. Default `false`.

- **Responses**:
  - `200 OK`: Successful comparison.
  ```json
  {
    "origin": "12.9257, 77.5833",
    "destination": "12.9501, 77.5847",
    "walkingMode": "pedestrian",
    "timestamp": "2026-10-27T17:25:00Z",
    "rankingReason": "Evidence-led Route ranks #1 because lighting verification and low tolerance for unmapped segments are prioritized.",
    "routes": [
      {
        "id": "route-evidence",
        "name": "Safety-prioritized Route",
        "preference": "Safety-prioritized",
        "category": "safety_prioritized",
        "departurePeriod": "night",
        "stepFree": false,
        "distanceMeters": 2721,
        "durationSeconds": 2268,
        "generalizedCost": 4857.74,
        "routeRisk": 0.3807,
        "adverseRiskScore": 0.2840,
        "evidenceCoverage": 0.45,
        "hasInsufficientEvidence": false,
        "overlapWithFastest": 0.82,
        "geometry": [[12.9257, 77.5833], [12.9290, 77.5831], [12.9501, 77.5847]],
        "characteristics": [
          "100.0% verified street lighting",
          "Walking distance 2721m (~37.8 min)",
          "Nearest police facility within 367m"
        ],
        "evidenceSummary": {
          "coverage": "limited",
          "coveragePercentage": 45,
          "freshestObservationDays": 8,
          "freshnessState": "fresh",
          "riskEstimate": "Route effective risk: 0.38 (composite scale 0-1)",
          "crimeCount": 0,
          "lightingCoveragePercentage": 100.0,
          "feedbackCount": 0,
          "nearestHospitalDistanceMeters": 743.0,
          "nearestPoliceDistanceMeters": 367.6,
          "dataQualitySummary": "45.0% evidence coverage across indicators"
        },
        "explanation": "Safety-prioritized route with high risk penalty (lambda=3.0). Strongly avoids unlit, conflicting, and higher-crime segments.",
        "explanationDetails": {
          "selection_reason": "Route was selected under Safety-prioritized objective (lambda=3.0).",
          "influential_segments": "Segment 10th Main Road (effective risk 0.18) guided route away from unlit alternatives.",
          "crime_evidence": "Traverses segments with zero verified historical crime records.",
          "lighting_evidence": "100.0% verified lit corridor during night departure period.",
          "dog_encounters": "No aggressive stray dog encounters reported.",
          "infrastructure_evidence": "92.0% dedicated sidewalk coverage.",
          "assistance_proximity": "Police assistance within 367m, hospital within 743m.",
          "uncertainty_and_prior": "Composite evidence coverage is 45.0%. Missing data filled with prior R_unknown=0.50.",
          "time_delta_vs_fastest": "Matches fastest direct walking time."
        },
        "tradeoffs": "Fastest route already follows the safest corridor; no additional walking detour needed.",
        "rankingFactors": [
          "Generalized cost: 4857.74",
          "Walking duration: 37.8 min",
          "Lit streets: 100.0%"
        ],
        "sourceMetadata": {
          "network": "OpenStreetMap pedestrian graph",
          "licensing": "ODbL 1.0",
          "algorithm": "Dijkstra / Yen loopless paths",
          "scoringModelVersion": "2.0.0"
        }
      }
    ]
  }
  ```

#### `GET /routes/sensitivity-analysis`
Executes an empirical sensitivity analysis benchmarking suite evaluating the stability of the SafePath v2.0 routing model across parameter sweeps.
- **Access**: Public
- **Evaluations Included**:
  1. $\lambda$ risk-priority trade-off sweep ($\lambda \in [0.0, 10.0]$).
  2. Lighting and diurnal temporal modulation sensitivity (`daytime`, `evening`, `night`).
  3. Stray dog encounter evidence differentiation (ordinary sightings vs aggressive barking vs bite incidents).
  4. Pedestrian infrastructure deficiencies (sidewalk absence, high crossing difficulty, active obstructions, step-free constraint).
  5. Missing-data prior sensitivity ($R_{\text{unknown}} \in [0.10, 0.90]$).
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "timestamp": "2026-11-01T14:15:00Z",
    "benchmark_graph_nodes": 6,
    "benchmark_graph_edges": 7,
    "evaluations": {
      "lambda_tradeoff": {},
      "lighting_and_temporal": {},
      "dog_encounter_differentiation": {},
      "infrastructure_and_accessibility": {},
      "missing_data_prior_sensitivity": {}
    },
    "key_findings": [
      "Lambda trade-off demonstrates clear bifurcation between travel-time minimization and risk aversion.",
      "Time-aware routing shifts preference toward illuminated corridors at night while keeping daytime routes direct.",
      "Calm dog sightings maintain route continuity whereas aggressive encounters trigger protective detours.",
      "Step-free constraint strictly avoids stairs while sidewalk availability improves infrastructure quality.",
      "Prior R_unknown=0.50 strikes a mathematically stable balance between optimism and undue detour penalties."
    ]
  }
  ```

#### `GET /evidence/segments?routeId={routeId}`
Fetches street-segment-level evidence quality, provenance, and network-matched indicators.
- **Access**: Public
- **Query Parameters**:
  - `routeId` (required): Route identifier (e.g. `route-evidence`, `route-test-area`).
- **Response `200 OK`**:
  ```json
  {
    "routeId": "route-evidence",
    "routeName": "Evidence-led Route",
    "segments": [
      {
        "id": "seg-10th-main-01",
        "streetName": "10th Main Road (4th Block to 3rd Block)",
        "source": "SafePath Geospatial Pipeline",
        "observedAt": "2026-10-18T00:00:00Z",
        "coverage": "adequate",
        "freshness": "fresh",
        "state": "available",
        "riskEstimate": "Evidence state: available; Lighting: lit; Crimes: 0",
        "limitations": [
          "Mapped streetlight status does not guarantee power grid operation or bulb functionality."
        ],
        "attributes": {
          "lighting": { "litStatus": "lit", "dataState": "present", "confidence": "high" },
          "policeAccess": { "distanceMeters": 420.0, "walkingTimeMinutes": 5.8, "distanceType": "network_walking" },
          "hospitalAccess": { "distanceMeters": 680.0, "walkingTimeMinutes": 9.4, "distanceType": "network_walking" },
          "crime": { "count": 0, "ratePerKm": 0.0, "indicatorType": "historical_crime_density" }
        },
        "timeline": [],
        "geometry": [[12.9257, 77.5833], [12.9290, 77.5831]],
        "edgeU": 101,
        "edgeV": 102,
        "edgeKey": 0,
        "lengthMeters": 333.0,
        "litStatus": "lit",
        "nearestPoliceDistanceMeters": 420.0,
        "nearestPoliceWalkingMinutes": 5.8,
        "nearestHospitalDistanceMeters": 680.0,
        "nearestHospitalWalkingMinutes": 9.4,
        "crimeCount": 0,
        "crimeRatePerKm": 0.0,
        "communityReportsCount": 0,
        "evidenceSummary": {}
      }
    ]
  }
  ```

#### `GET /evidence/observations`
Queries privacy-sanitized atomic evidence observations associated with pedestrian network segments.
Strictly excludes all reporter identities, user IDs, phone numbers, and emails.
- **Access**: Public
- **Query Parameters**:
  - `category` (optional): Filter by evidence category (`crime`, `lighting`, `facility_access`, `community_hazard`, `safety_incident`, `civic_observation`).
  - `sourceType` (optional): Filter by source type (`crime_dataset`, `osm_lighting`, `osm_facility`, `community_report`).
  - `dataState` (optional): Filter by data state (`present`, `missing`, `stale`, `conflicting`, `insufficient`).
  - `verificationStatus` (optional): Filter by verification (`admin_reviewed_community_report`, `unverified_community_submission`, `documented_crime_record`, `official_osm_attribute`).
  - `segmentId` (optional): Filter by associated street segment ID.
  - `limit` (optional, default 50, max 200): Pagination page size.
  - `offset` (optional, default 0): Pagination offset.
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "obs-cm-rep-test-01",
        "sourceId": "rep-test-01",
        "sourceType": "community_report",
        "category": "community_hazard",
        "subcategory": "harassment",
        "latitude": 12.9315,
        "longitude": 77.5850,
        "geometry": { "type": "Point", "coordinates": [77.5850, 12.9315] },
        "segmentId": "seg-test-area-101-102-0",
        "edgeU": 101,
        "edgeV": 102,
        "edgeKey": 0,
        "matchDistanceMeters": 5.2,
        "matchMethod": "strtree_project",
        "matchStatus": "matched",
        "observedAt": "2026-10-22T14:30:00Z",
        "ingestedAt": "2026-10-22T14:30:00Z",
        "sourceAttribution": "SafePath Community Contributor (PII Stripped)",
        "verificationStatus": "admin_reviewed_community_report",
        "severity": null,
        "confidence": "moderate",
        "dataState": "present",
        "provenance": "Community Report Submission",
        "limitations": [
          "Community report reflects individual perception.",
          "Administrative approval confirms display suitability, not absolute ground-truth certainty."
        ],
        "attributes": {
          "description": "Persistent catcalling near bus stand",
          "corroborations": 2
        }
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
  ```

#### `POST /evidence/import-crime`
Validates and ingests a supplied CSV historical crime dataset. Rejects datasets containing personal identifying information (PII) such as victim/suspect names, phone numbers, or addresses.
- **Access**: Admin / Pipeline
- **Request**: Multipart `file` (CSV upload) OR JSON `{ "filePath": "/path/to/dataset.csv" }`.
- **Minimal Required CSV Columns**: `latitude`, `longitude`, `category` (or aliases `lat`, `lon`, `offense`).
- **Responses**:
  - `200 OK`:
    ```json
    {
      "isLoaded": true,
      "recordCount": 6,
      "validCount": 6,
      "skippedCount": 0,
      "duplicateCount": 0,
      "dateRange": ["2026-05-14", "2026-10-02"],
      "categories": ["assault", "burglary", "harassment", "robbery", "theft", "vandalism"],
      "limitations": [
        "Incident density reflects reporting practices and exposure.",
        "Historical indicators must not be interpreted as individual victimization probabilities."
      ],
      "sourceName": "example_crime_dataset.csv"
    }
    ```
  - `422 Unprocessable Entity`: Missing required columns or prohibited PII columns detected (`name`, `victim`, `suspect`, `phone`, `email`, `address`).

#### `POST /evidence/process-pipeline`
Executes the comprehensive evidence processing and spatial matching pipeline for the active study area:
1. Loads and spatially indexes the pedestrian street network.
2. Classifies lighting with epistemological distinction (`lit`, `unlit`, `conflicting`, `unmapped`).
3. Computes network walking distance and estimated walking time to police stations and hospitals.
4. Normalizes historical crime counts per kilometer (within stated temporal window).
5. Maps and deduplicates community reports with strict privacy detachment.
6. Persists `StreetSegment` and `EvidenceObservation` database records.
- **Access**: Admin / Pipeline
- **Request Body** (optional):
  ```json
  {
    "crimeFilePath": "backend/data/example_crime_dataset.csv"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "studyAreaName": "Bengaluru Central Pedestrian Research Corridor",
    "edgesProcessed": 482,
    "observationsPersisted": 128,
    "crimeObservationsMatched": 6,
    "lightingObservationsRecorded": 82,
    "facilitiesMapped": 8,
    "communityReportsMatched": 14,
    "executionTimeSeconds": 2.45,
    "status": "success"
  }
  ```

#### `GET /evidence/coverage`
Returns data coverage metrics, known evidence gaps, and scientific caveats for the active study area.
- **Access**: Public
- **Response `200 OK`**:
  ```json
  {
    "studyAreaName": "Bengaluru Central Pedestrian Research Corridor",
    "totalEdges": 482,
    "edgesWithLighting": 82,
    "lightingCoveragePercentage": 17.01,
    "litEdgesCount": 68,
    "unlitEdgesCount": 14,
    "conflictingLightingEdgesCount": 2,
    "unmappedLightingEdgesCount": 398,
    "policeStationsCount": 4,
    "policeAccessibleEdgesCount": 380,
    "policeAccessiblePercentage": 78.8,
    "hospitalsCount": 5,
    "hospitalAccessibleEdgesCount": 412,
    "hospitalAccessiblePercentage": 85.5,
    "crimeIncidentsMatched": 6,
    "communityReportsMatched": 14,
    "dataStateBreakdown": {
      "present": 102,
      "missing": 398,
      "conflicting": 2,
      "stale": 3
    },
    "dataGaps": [
      "398 street segments (82.6%) lack explicit OpenStreetMap lighting tags.",
      "Official crime incident records in this jurisdiction are not openly published as point-level GPS data.",
      "Emergency facility operating hours and staffing status are unverified in OpenStreetMap."
    ],
    "caveats": [
      "Absence of evidence is never treated as evidence of zero risk or safety.",
      "Proximity to a police station or hospital does not imply low crime risk.",
      "Mapped streetlights are not guaranteed to be functioning or turned on during nighttime journeys."
    ]
  }
  ```


#### `GET /journeys`
Lists saved journeys belonging to the authenticated traveller.
- **Access**: Authenticated (`Bearer`)
- **Response `200 OK`**: `List[SavedJourneyResponse]`

#### `POST /journeys`
Saves a planned walking journey.
- **Access**: Authenticated (`Bearer`)
- **Request Body**:
  ```json
  {
    "start": "MG Road",
    "end": "Cubbon Park",
    "routeId": "route-evidence",
    "routeName": "Evidence-led Route",
    "distanceMeters": 1850,
    "durationMinutes": 24,
    "preferences": { "lightingWeight": 50 }
  }
  ```
- **Response `201 Created`**: SavedJourney object.

#### `DELETE /journeys/{id}`
Deletes a saved journey. **IDOR protected**: Users can only delete their own journeys.
- **Access**: Authenticated (`Bearer`)
- **Response `200 OK`**: `{"status": "ok", "message": "Journey deleted successfully."}`

#### `GET /journeys/history`
Returns completed walking trip history with arrival confirmations.
- **Access**: Authenticated (`Bearer`)
- **Response `200 OK`**: `List[JourneyHistoryResponse]`

#### `GET /saved-places` & `POST /saved-places` & `DELETE /saved-places/{id}`
Manages quick origin/destination bookmarks (Home, Office, Transit).
- **Access**: Authenticated (`Bearer`)

---

### 3.3 Community Reports & Trusted Journeys

#### `POST /reports`
Submits a community infrastructure observation or dog encounter report. Automatically flags critical safety keywords and dog bites (`dog_bite`) for urgent moderator review.
- **Access**: Public / Authenticated (user ID captured if authenticated)
- **Supported Categories**:
  - `broken_lighting`: Broken / unlit street lighting
  - `blocked_footpath`: Blocked footpath / sidewalk obstruction
  - `poor_visibility`: Poor visibility / blind curve / overgrown foliage
  - `construction_hazard`: Construction or pavement hazard
  - `access_facility`: Access / public transit facility
  - `dog_sighting`: Ordinary stray dog sighting (calm / informational)
  - `dog_group`: Group or pack of stray dogs
  - `dog_aggressive`: Aggressive encounter (barking, chasing, threatening behaviour)
  - `dog_bite`: Physical bite incident or animal attack (auto-flagged)
  - `other_concern`: Other street condition
- **Request Body**:
  ```json
  {
    "category": "dog_aggressive",
    "location": "Lalbagh West Gate approach",
    "description": "Two dogs barked and chased cyclist near the park gate.",
    "latitude": 12.9460,
    "longitude": 77.5844,
    "encounterTime": "2026-10-27T14:15:00Z",
    "dogCount": 2,
    "isAggressive": true,
    "anonymous": true
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "rep-uuid",
    "category": "dog_aggressive",
    "categoryLabel": "Aggressive dog encounter",
    "location": "Lalbagh West Gate approach",
    "description": "Two dogs barked and chased...",
    "status": "pending",
    "latitude": 12.9460,
    "longitude": 77.5844,
    "dogCount": 2,
    "isAggressive": true,
    "encounterTime": "2026-10-27T14:15:00Z",
    "createdAt": "2026-10-27T14:16:00Z"
  }
  ```

#### `POST /reports/{id}/corroborate`
Allows a distinct authenticated user to corroborate or confirm a reported street hazard, lighting failure, or animal encounter.
- **Access**: Authenticated (`Bearer`)
- **Anti-Abuse Controls**:
  - Submitter cannot corroborate their own report (`400 Bad Request`).
  - An account can corroborate a given report only once (`400 Bad Request`). Enforced via unique database constraint `(report_id, user_id)`.
- **Response `200 OK`**:
  ```json
  {
    "message": "Community report corroborated successfully.",
    "reportId": "rep-uuid",
    "corroborationsCount": 2,
    "userHasCorroborated": true
  }
  ```

#### `GET /reports/public`
Dedicated public map evidence feed returning strictly approved reports with **all reporter PII excluded**.
- **Access**: Public
- **Query Parameters**: `category` (optional)
- **Response `200 OK`**: Array of sanitized incident points containing coordinates, categories, encounter time, count, aggressiveness, status, and description. User IDs, emails, phone numbers, and full names are strictly excluded.

#### `PUT /reports/{id}`
Allows an authenticated reporter to correct or update their own submitted report.
- **Access**: Authenticated (`Bearer`) — strict ownership check (`reporter_id == current_user.id`). Foreign modification attempts return `403 Forbidden` (anti-IDOR).
- **Request Body**: `ReportUpdate` (`description`, `category`, `location`, `latitude`, `longitude`, `locationConfidence`, `dogCount`, `isAggressive`, `encounterTime`).
- **Response `200 OK`**: Updated sanitized report representation.

#### `DELETE /reports/{id}`
Allows an authenticated reporter to withdraw their own report. Soft-withdraws report by setting `status = "rejected"` with `moderator_notes = "Withdrawn by submitter"` so it is immediately removed from public routing evidence and map layers.
- **Access**: Authenticated (`Bearer`) — strict ownership check. Foreign withdrawal attempts return `403 Forbidden`.
- **Response `200 OK`**: `{"message": "Report successfully withdrawn.", "id": "rep-uuid", "status": "rejected"}`.

#### `GET /reports`
Lists public community reports with pagination and filtering across categories and moderation statuses.
- **Access**: Public
- **Query Parameters**: `category`, `status` (defaults to excluding rejected), `query`, `page`, `pageSize`
- **Response `200 OK`**: Envelope containing items list and total count. Zero reporter PII exposed for anonymous submissions.

#### `GET /reports/mine`
Lists reports submitted by the current authenticated traveller across all moderation states.
- **Access**: Authenticated (`Bearer`)
- **Response `200 OK`**: List of reports submitted by the caller.

#### `GET /trusted-contacts` & `POST /trusted-contacts` & `PATCH /trusted-contacts/{id}` & `DELETE /trusted-contacts/{id}`
CRUD operations for emergency and trusted contacts.
- **Access**: Authenticated (`Bearer`)
- **Field-Level Encryption at Rest**: `name` and `phone` are encrypted using AES-128 Fernet before storage in the database. Encryption keys are loaded from environment variables and held strictly separate from the database.
- **Strict Data Isolation (IDOR Prevention)**: Queries enforce `user_id == current_user.id`. Modifying or deleting a foreign contact returns `403 Forbidden`.
- **Validation**: Phone numbers are validated against standard format (`^\+?[0-9\s\-()]{7,25}$`).
- **Administrative Privacy**: Plaintext contact names and phones are never exposed in ordinary administrative views or logs.

#### `POST /feedback`
Submits feedback, observations on lighting accuracy, or bug reports.
- **Access**: Public / Authenticated (user ID captured only when authenticated; supports anonymous submissions)
- **Request Body**:
  ```json
  {
    "category": "lighting_accuracy",
    "message": "Streetlights along Lalbagh West Gate are now operational.",
    "rating": 5
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "fb-uuid",
    "category": "lighting_accuracy",
    "message": "Streetlights along Lalbagh West Gate are now operational.",
    "rating": 5,
    "status": "new",
    "createdAt": "2026-10-27T15:30:00Z",
    "isAnonymous": false
  }
  ```

#### `POST /journey-shares`
Initiates a journey ETA notification to trusted contacts. Discloses real delivery status.
- **Access**: Authenticated (`Bearer`)
- **Request Body**:
  ```json
  {
    "routeName": "Evidence-led Route",
    "etaMinutes": 24,
    "destination": "Cubbon Park Gate",
    "contactIds": ["contact-uuid"]
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "deliveryStatus": "pending_provider_integration",
    "providerName": "Twilio / WhatsApp Business API (Not configured in prototype)",
    "deliveredCount": 0,
    "intendedCount": 1,
    "shareLink": "https://safepath.org/track/share-token",
    "previewMessage": "I am walking along Evidence-led Route to Cubbon Park Gate. ETA: 24 mins."
  }
  ```

#### `POST /arrival-confirmations`
Records destination arrival.
- **Access**: Authenticated (`Bearer`)
- **Response `200 OK`**:
  ```json
  {
    "arrivalConfirmed": true,
    "timestamp": "2026-10-27T14:30:00Z",
    "deliveryStatus": "pending_provider_integration",
    "message": "Arrival recorded locally. Telephony notification pending gateway integration."
  }
  ```

---

### 3.4 Administration & Governance

#### `GET /admin/reports`
Lists reports for moderation with search, filtering, and pagination.
- **Access**: Moderator or Administrator (`require_moderator_or_admin`)
- **Query Parameters**: `status` (`pending`, `approved`, `rejected`, `flagged`), `query`, `page`, `pageSize`
- **Response `200 OK`**: Paginated envelope with reports.

#### `PATCH /admin/reports/{id}`
Updates moderation status. Requires an audit reason and validates legal state transitions.
- **Access**: Moderator or Administrator
- **Request Body**:
  ```json
  {
    "status": "approved",
    "reason": "Verified municipal maintenance ticket filed."
  }
  ```
- **Response `200 OK`**: Updated report object.

#### `GET /admin/users`
Lists user directory with default privacy minimization. Plaintext names, emails, and phone numbers are excluded.
- **Access**: Administrator (`require_admin`)
- **Query Parameters**: `query`, `page`, `pageSize`
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "usr-uuid",
        "displayName": "User-usr-uuid",
        "emailMasked": "j***e@e***e.com",
        "role": "traveller",
        "status": "active",
        "joinedAt": "2026-10-27T14:00:00Z",
        "reportsCount": 3,
        "savedPlansCount": 5
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 20
  }
  ```

#### `POST /admin/users/{id}/reveal-identity`
Authorized identity revelation for account support. Access is strictly permission-protected and audited.
- **Access**: Administrator (`require_admin`)
- **Request Body**:
  ```json
  {
    "reason": "Account recovery support ticket #SUP-8821"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "id": "usr-uuid",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "role": "traveller",
    "status": "active",
    "revealedAt": "2026-10-27T15:35:00Z",
    "revealedBy": "admin@safepath.org",
    "justification": "Account recovery support ticket #SUP-8821"
  }
  ```

#### `GET /admin/feedback`
Administrative feedback inbox.
- **Access**: Moderator or Administrator (`require_moderator_or_admin`)
- **Query Parameters**: `category`, `status` (`new`, `in_review`, `resolved`, `dismissed`), `page`, `pageSize`
- **Response `200 OK`**: Paginated envelope of feedback submissions.

#### `PATCH /admin/feedback/{id}`
Updates feedback triage status and attaches administrative resolution notes.
- **Access**: Moderator or Administrator
- **Request Body**:
  ```json
  {
    "status": "resolved",
    "adminNotes": "Fixed in streetlight dataset update v1.4"
  }
  ```
- **Response `200 OK`**: Updated feedback item.

#### `PATCH /admin/users/{id}`
Updates user role or activation status.
- **Access**: Administrator
- **Request Body**:
  ```json
  {
    "role": "moderator",
    "status": "active"
  }
  ```
- **Response `200 OK`**: Updated user object.

#### `GET /admin/data-sources`
Monitors health, coverage, and freshness of upstream evidence registries.
- **Access**: Moderator or Administrator
- **Response `200 OK`**: Paginated envelope of data sources.

#### `GET /admin/audit`
Returns append-only audit trail logs.
- **Access**: Administrator
- **Response `200 OK`**: Paginated envelope of audit logs.

#### `GET /admin/settings` & `PATCH /admin/settings`
Reads and updates global governance thresholds (stale days, auto-flag keywords, weighting factors).
- **Access**: Administrator
- **Response `200 OK`**: Current system settings object.

---

## 5. Phase 3: Explainable Map Experience, Community Trust & Journey Protection

### 5.1 Evidence Map Layers Bundle

#### `GET /evidence/map-layers`
Returns aggregated geospatial evidence layers partitioned by classification for client-side multi-layer rendering and independent layer toggling without triggering Dijkstra route recomputation.
- **Access**: Public
- **Query Parameters**:
  - `studyArea` (optional, default `"default"`): Target study area boundary.
- **Response `200 OK`**:
  ```json
  {
    "studyArea": "default",
    "timestamp": "2026-11-01T14:00:00Z",
    "safetyDisclaimer": "SafePath Finder provides descriptive, historical, and community-reported evidence for informational purposes only. It is NOT an emergency dispatch service and does not guarantee personal safety.",
    "layers": {
      "facilities": [
        {
          "id": "fac-001",
          "name": "Central Police Station",
          "category": "police",
          "coordinates": [12.9716, 77.5946],
          "type": "official_presence",
          "dataSource": "Bengaluru Police GIS Registry"
        }
      ],
      "landmarks": [
        {
          "id": "lmk-001",
          "name": "MG Road Metro Station",
          "category": "transit_hub",
          "coordinates": [12.9756, 77.6066],
          "type": "natural_surveillance"
        }
      ],
      "dogs": [
        {
          "id": "dog-001",
          "category": "pack",
          "severity": "caution",
          "coordinates": [12.973, 77.598],
          "encounterTime": "2026-10-31T20:30:00Z",
          "packSize": 4,
          "verified": true,
          "corroborations": 3,
          "outdatedFlags": 0
        }
      ],
      "communityReports": [
        {
          "id": "rep-001",
          "category": "street_lighting",
          "coordinates": [12.974, 77.601],
          "observedAt": "2026-10-31T21:15:00Z",
          "status": "published",
          "corroborationsCount": 5,
          "outdatedFlags": 1
        }
      ],
      "lighting": [
        {
          "segmentId": "seg-101",
          "geometry": [[12.971, 77.594], [12.973, 77.596]],
          "litStatus": "well_lit",
          "lumensEstimated": 32.5,
          "source": "Municipal Streetlight Audit 2026"
        }
      ],
      "pedestrianInfra": [
        {
          "segmentId": "seg-101",
          "sidewalkPresent": true,
          "surfaceQuality": "good",
          "crossingType": "signalized"
        }
      ],
      "crimeObservations": [
        {
          "id": "cr-001",
          "incidentType": "theft",
          "coordinates": [12.972, 77.595],
          "timePeriod": "night",
          "source": "State Crime Records Bureau (Anonymized)"
        }
      ]
    },
    "legendSections": {
      "mappedData": [
        {"layer": "facilities", "description": "Verified police posts and hospitals", "reliability": "official_registry"},
        {"layer": "lighting", "description": "Municipal lighting survey and photometric measurements", "reliability": "government_audit"}
      ],
      "communityReports": [
        {"layer": "communityReports", "description": "Traveller-submitted observations pending or confirmed", "reliability": "crowdsourced_subject_to_decay"},
        {"layer": "dogs", "description": "Canine sightings, packs, and encounters", "reliability": "crowdsourced_corroborated"}
      ],
      "inferredValues": [
        {"layer": "visibilityScores", "description": "Calculated pedestrian field-of-view and natural surveillance scores", "reliability": "algorithmic_inference"}
      ],
      "unknownInfo": [
        {"layer": "unmappedStreets", "description": "Streets lacking photometric audits or recent community observations", "reliability": "epistemic_uncertainty_r_unknown"}
      ]
    }
  }
  ```

---

### 5.2 Community Report Reliability & Confirmations

#### `POST /reports/{report_id}/confirm`
Confirms that a reported community observation remains active and accurate.
- **Access**: Authenticated Traveller
- **Idempotency & Anti-Gaming**:
  - Submitter cannot confirm their own report (`400 Bad Request`).
  - If user previously flagged the report as outdated, the outdated flag is automatically retracted and moved to active confirmation.
  - Repeated confirmation returns the existing confirmation (`200 OK`).
- **Response `200 OK`**:
  ```json
  {
    "message": "Report confirmed as still active.",
    "reportId": "rep-001",
    "corroborationsCount": 6,
    "outdatedFlags": 0,
    "userAction": "confirm"
  }
  ```

#### `POST /reports/{report_id}/outdated`
Flags a community report as outdated, resolved, or no longer reflecting current street conditions.
- **Access**: Authenticated Traveller
- **Idempotency & Anti-Gaming**:
  - Submitter cannot flag their own report (`400 Bad Request`).
  - If user previously confirmed the report, the confirmation is retracted and moved to outdated flag.
- **Response `200 OK`**:
  ```json
  {
    "message": "Report flagged as outdated or resolved.",
    "reportId": "rep-001",
    "corroborationsCount": 5,
    "outdatedFlags": 1,
    "userAction": "outdated"
  }
  ```

#### `GET /reports/mine`
Retrieves all reports submitted by the authenticated traveller with moderation lifecycle tracking.
- **Access**: Authenticated Traveller
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "rep-001",
        "category": "street_lighting",
        "subCategory": "dark_stretch",
        "title": "Streetlight fixture unpowered",
        "status": "published",
        "observedAt": "2026-10-31T20:00:00Z",
        "createdAt": "2026-10-31T20:15:00Z",
        "coordinates": [12.974, 77.601],
        "corroborationsCount": 4,
        "outdatedFlags": 0
      }
    ],
    "total": 1
  }
  ```

---

### 5.3 Trusted-Contact Journey Protection Sessions

#### `POST /journey-sessions/start`
Starts a walk journey session with explicit voluntary user consent, ETA, and trusted contact notifications.
- **Access**: Authenticated Traveller
- **Request Body**:
  ```json
  {
    "origin": [12.9716, 77.5946],
    "destination": [12.9756, 77.6066],
    "routeName": "Safety-prioritized Route",
    "routeId": "route-safe-01",
    "etaMinutes": 18,
    "distanceMeters": 1420.0,
    "contactIds": ["ct-001", "ct-002"],
    "consentGiven": true
  }
  ```
- **Responses**:
  - `201 Created`:
    ```json
    {
      "id": "js-uuid",
      "token": "sec-token-hex-32",
      "status": "in_progress",
      "origin": [12.9716, 77.5946],
      "destination": [12.9756, 77.6066],
      "routeName": "Safety-prioritized Route",
      "etaMinutes": 18,
      "distanceMeters": 1420.0,
      "contactCount": 2,
      "startedAt": "2026-11-01T14:30:00Z",
      "expectedArrivalAt": "2026-11-01T14:48:00Z",
      "expiresAt": "2026-11-01T18:30:00Z",
      "notificationMode": "simulated_development_mode",
      "shareUrl": "/safepath_pro.html?share_token=sec-token-hex-32"
    }
    ```
  - `400 Bad Request`: Voluntary consent not given (`consentGiven: false`).

#### `POST /journey-sessions/{session_id}/check-in`
Safely concludes an active journey session ("I Have Arrived Safely").
- **Access**: Authenticated Traveller (session owner)
- **Responses**:
  - `200 OK`:
    ```json
    {
      "id": "js-uuid",
      "status": "completed",
      "completedAt": "2026-11-01T14:45:00Z",
      "message": "Journey completed safely. Trusted contacts notified."
    }
    ```
  - `400 Bad Request`: Session already completed (idempotency guard) or revoked.

#### `POST /journey-sessions/{session_id}/cancel`
Revokes or cancels an active journey session.
- **Access**: Authenticated Traveller (session owner)
- **Response `200 OK`**:
  ```json
  {
    "id": "js-uuid",
    "status": "cancelled",
    "isRevoked": true,
    "message": "Journey session cancelled."
  }
  ```

#### `GET /journey-sessions/active`
Retrieves the authenticated traveller's current in-progress journey session if active.
- **Access**: Authenticated Traveller
- **Response `200 OK`**: Current `JourneySessionResponse` or `null`.

#### `POST /journey-sessions/{session_id}/simulate-reminder`
Simulates a 5-minute pre-arrival reminder notification for demonstration and verification purposes.
- **Access**: Authenticated Traveller (session owner)
- **Response `200 OK`**:
  ```json
  {
    "id": "js-uuid",
    "reminderSent": true,
    "notificationMode": "simulated_development_mode",
    "message": "Simulated pre-arrival reminder triggered."
  }
  ```

#### `GET /journey-shares/public/{token}`
Tokenized public view for trusted contacts without requiring SafePath login credentials.
- **Access**: Public (bearer token in URL path)
- **Privacy & Security Guarantee**: **Zero creator PII leaked**. Creator name, user ID, email, and phone are never exposed in this payload.
- **Response `200 OK`**:
  ```json
  {
    "token": "sec-token-hex-32",
    "status": "in_progress",
    "origin": [12.9716, 77.5946],
    "destination": [12.9756, 77.6066],
    "routeName": "Safety-prioritized Route",
    "etaMinutes": 18,
    "distanceMeters": 1420.0,
    "startedAt": "2026-11-01T14:30:00Z",
    "expectedArrivalAt": "2026-11-01T14:48:00Z",
    "completedAt": null,
    "isRevoked": false,
    "isExpired": false,
    "disclaimer": "This page provides peer-to-peer journey reassurance for trusted contacts. SafePath Finder does NOT provide emergency dispatch or monitor active physical safety. If you believe the traveller is in immediate danger, contact official emergency services (112) directly.",
    "peerReassuranceNotice": "Peer-to-peer journey status sharing. Not an active surveillance or emergency dispatch service. Missed check-in does not confirm emergency."
  }
  ```
- **Responses on Invalidation**:
  - `404 Not Found`: Invalid or revoked token.
  - `410 Gone`: Expired journey session.

---

## 6. Operational Health & Error Codes

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Root operational health check |
| `/api/v1/health` | `GET` | API v1 operational health check |
| `/api/v1/evidence/map-layers` | `GET` | Aggregated geospatial layer bundle & legend |
| `/api/v1/journey-shares/public/{token}` | `GET` | Non-authenticated public trip viewer |
| `/api/docs` | `GET` | Interactive Swagger UI documentation |
| `/api/redoc` | `GET` | ReDoc API documentation |
| `/api/openapi.json` | `GET` | OpenAPI 3.1 specification schema |

### HTTP Status Code Usage
- `200 OK`: Request succeeded.
- `201 Created`: Resource created.
- `202 Accepted`: Asynchronous operation or privacy-preserving request accepted.
- `400 Bad Request`: Business rule validation error.
- `401 Unauthorized`: Missing or invalid authentication token.
- `403 Forbidden`: Insufficient role permissions or IDOR violation.
- `404 Not Found`: Resource does not exist.
- `410 Gone`: Resource expired (e.g., journey share token).
- `422 Unprocessable Entity`: Request schema validation error.
- `429 Too Many Requests`: Rate limit exceeded (e.g. password reset rate limiting).
- `500 Internal Server Error`: Unhandled server exception.


