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
Compares walking-route alternatives using transparent multi-attribute utility ranking and explainable trade-offs. Computes primary routes via separate Dijkstra runs on a directed weighted pedestrian network, plus distinct loopless alternatives via Yen's K-shortest paths algorithm. Validates origin and destination coordinates against the active study area boundary.

- **Generalized Edge Cost**:
  $$\text{Cost}_e = T_e \times (1 + \lambda \times R_{\text{effective}_e})$$
  - **Fastest**: $\lambda = 0$ (minimizes pedestrian traversal time $\sum T_e$).
  - **Balanced**: $\lambda = \lambda_{\text{balanced}} > 0$ (default `1.0`).
  - **Safety-prioritized**: $\lambda = \lambda_{\text{safety}} > \lambda_{\text{balanced}}$ (default `3.0`).
- **Effective Risk Formula**:
  $$R_{\text{effective}} = Q \times R_{\text{observed}} + (1 - Q) \times R_{\text{unknown}}$$
  where $Q$ is composite evidence coverage across verified lighting, assistance access, crime records, and community feedback. Missing evidence is never encoded as zero risk.
- **Alternatives**: Yen's K-shortest loopless paths with Jaccard edge overlap filtering ($< 0.80$).

- **Access**: Public
- **Request Body**:
  ```json
  {
    "origin": "12.9257, 77.5833",
    "destination": "12.9501, 77.5847",
    "walkingMode": "pedestrian",
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
- **Responses**:
  - `200 OK`: Successful comparison.
  - `400 Bad Request`: Coordinate falls outside configured study area, or origin and destination lie in disconnected network components.
  - `422 Unprocessable Entity`: Coordinate values outside valid mathematical latitude/longitude range.
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
        "distanceMeters": 2721,
        "durationSeconds": 2268,
        "generalizedCost": 4857.74,
        "routeRisk": 0.3807,
        "evidenceCoverage": 0.45,
        "hasInsufficientEvidence": false,
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
        "tradeoffs": "Fastest route already follows the safest corridor; no additional walking detour needed.",
        "rankingFactors": [
          "Generalized cost: 4857.74",
          "Walking duration: 37.8 min",
          "Lit streets: 100.0%"
        ],
        "sourceMetadata": {
          "network": "OpenStreetMap pedestrian graph",
          "licensing": "ODbL 1.0",
          "algorithm": "Dijkstra / Yen loopless paths"
        }
      }
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
Submits a community infrastructure observation. Automatically flags reports containing critical safety keywords for urgent moderator review.
- **Access**: Public / Authenticated (user ID captured if authenticated)
- **Request Body**:
  ```json
  {
    "category": "broken_lighting",
    "location": "Lalbagh West Gate approach",
    "description": "Streetlight fixture 14-B flickering and unlit between nursery and main gate."
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "rep-uuid",
    "category": "broken_lighting",
    "categoryLabel": "Broken / unlit street lighting",
    "location": "Lalbagh West Gate approach",
    "description": "Streetlight fixture 14-B flickering...",
    "status": "pending",
    "createdAt": "2026-10-27T14:15:00Z"
  }
  ```

#### `GET /reports`
Lists public, approved reports for map overlay and incident exploration.
- **Access**: Public
- **Query Parameters**: `category`, `status` (defaults to approved)
- **Response `200 OK`**: List of approved reports.

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

## 4. Operational Health & Error Codes

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Root operational health check |
| `/api/v1/health` | `GET` | API v1 operational health check |
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
- `422 Unprocessable Entity`: Request schema validation error.
- `429 Too Many Requests`: Rate limit exceeded (e.g. password reset rate limiting).
- `500 Internal Server Error`: Unhandled server exception.

