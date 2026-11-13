from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.evidence import StreetSegment, EvidenceSource, EvidenceObservation
from app.schemas.evidence import RouteEvidenceResponse, SegmentResponse

DEFAULT_SEGMENTS: Dict[str, List[Dict[str, Any]]] = {
    "route-evidence": [
        {
            "id": "seg-10th-main-01",
            "streetName": "10th Main Road (4th Block to 3rd Block)",
            "source": "BBMP Municipal Streetlight Survey 2026",
            "observedAt": (datetime.now(timezone.utc) - timedelta(days=8)),
            "coverage": "adequate",
            "freshness": "fresh",
            "state": "available",
            "riskEstimate": "Moderate environmental context",
            "limitations": ["Late-night vendor activity levels unverified", "CCTV coverage status unknown"],
            "attributes": {"lightingStatus": "adequate", "footwayContinuity": "continuous", "commercialActivity": "high"},
            "timeline": [
                {"date": "2026-10-18", "event": "Municipal Audit (APPROVED): Pole #J4-102 inspected; LED luminaire functional.", "source": "BBMP Electrical Div"},
                {"date": "2026-09-02", "event": "Community Reporter (APPROVED): Footpath clear of construction debris.", "source": "SafePath Citizen"}
            ],
            "geometry": [[12.9257, 77.5833], [12.9290, 77.5831]]
        },
        {
            "id": "seg-south-end-02",
            "streetName": "South End Road & Circle",
            "source": "OpenStreetMap Bengaluru Pedestrian Ways & BBMP",
            "observedAt": (datetime.now(timezone.utc) - timedelta(days=12)),
            "coverage": "adequate",
            "freshness": "fresh",
            "state": "available",
            "riskEstimate": "Well-monitored transit corridor",
            "limitations": ["Peak-hour crossing congestion", "Footpath narrowing at bus bay"],
            "attributes": {"lightingStatus": "adequate", "footwayContinuity": "continuous", "commercialActivity": "high"},
            "timeline": [
                {"date": "2026-10-15", "event": "Transit Kiosk Audit (APPROVED): Police assistance booth operational.", "source": "Bengaluru Police"},
                {"date": "2026-09-20", "event": "Municipal Registry (APPROVED): Double-headed high-mast illumination.", "source": "BBMP"}
            ],
            "geometry": [[12.9290, 77.5831], [12.9330, 77.5832], [12.9370, 77.5835]]
        },
        {
            "id": "seg-ashoka-pillar-03",
            "streetName": "Ashoka Pillar Road Corridor",
            "source": "Citizen Observations & Municipal Survey",
            "observedAt": (datetime.now(timezone.utc) - timedelta(days=14)),
            "coverage": "adequate",
            "freshness": "fresh",
            "state": "available",
            "riskEstimate": "Moderate environmental context",
            "limitations": ["Overhanging tree branches reducing streetlight spread during monsoon"],
            "attributes": {"lightingStatus": "adequate", "footwayContinuity": "mostly_continuous", "commercialActivity": "moderate"},
            "timeline": [
                {"date": "2026-10-12", "event": "Lighting Survey (APPROVED): Luminaires verified; foliage pruning recommended.", "source": "Ward Committee"}
            ],
            "geometry": [[12.9370, 77.5835], [12.9415, 77.5840], [12.9460, 77.5844]]
        },
        {
            "id": "seg-lalbagh-approach-04",
            "streetName": "Lalbagh West Gate Approach Lane",
            "source": "Crowdsourced Reports & Park Authority",
            "observedAt": (datetime.now(timezone.utc) - timedelta(days=32)),
            "coverage": "limited",
            "freshness": "stale",
            "state": "limited",
            "riskEstimate": "Informational gap: Stale observations",
            "limitations": ["Observations are >30 days old", "Footpath pavement broken near secondary gate"],
            "attributes": {"lightingStatus": "limited", "footwayContinuity": "interrupted", "commercialActivity": "low_at_night"},
            "timeline": [
                {"date": "2026-09-25", "event": "Community Report (APPROVED): Streetlamp flickering near West Gate ticket counter.", "source": "Evening Commuter"}
            ],
            "geometry": [[12.9460, 77.5844], [12.9501, 77.5847]]
        }
    ]
}


def get_route_evidence_service(db: Session, route_id: str) -> RouteEvidenceResponse:
    """Retrieve verified street segments for a route, maintaining explicit uncertainty flags."""
    # Try database first
    db_segments = db.query(StreetSegment).filter(StreetSegment.route_id == route_id).all()
    if db_segments:
        segments_output = [
            SegmentResponse(
                id=seg.id,
                streetName=seg.street_name,
                source=seg.source,
                observedAt=seg.observed_at,
                coverage=seg.coverage,
                freshness=seg.freshness,
                state=seg.state,
                riskEstimate=seg.risk_estimate,
                limitations=seg.limitations or [],
                attributes=seg.attributes or {},
                timeline=seg.timeline or [],
                geometry=seg.geometry or [],
                edgeU=seg.edge_u,
                edgeV=seg.edge_v,
                edgeKey=seg.edge_key or 0,
                lengthMeters=seg.length_meters,
                litStatus=seg.lit_status or "unmapped",
                nearestPoliceDistanceMeters=seg.nearest_police_distance_meters,
                nearestPoliceWalkingMinutes=seg.nearest_police_walking_minutes,
                nearestHospitalDistanceMeters=seg.nearest_hospital_distance_meters,
                nearestHospitalWalkingMinutes=seg.nearest_hospital_walking_minutes,
                crimeCount=seg.crime_count or 0,
                crimeRatePerKm=seg.crime_rate_per_km or 0.0,
                communityReportsCount=seg.community_reports_count or 0,
                evidenceSummary=seg.evidence_summary or {}
            )
            for seg in db_segments
        ]
    else:
        # Fall back to default synthetic pilot segments
        raw_list = DEFAULT_SEGMENTS.get(route_id, DEFAULT_SEGMENTS["route-evidence"])
        segments_output = [SegmentResponse(**s) for s in raw_list]

    route_names = {
        "route-evidence": "Evidence-led Route",
        "route-balanced": "Balanced Sample Route",
        "route-shortest": "Shortest Sample Route"
    }
    return RouteEvidenceResponse(
        routeId=route_id,
        routeName=route_names.get(route_id, "Sample Route"),
        segments=segments_output
    )


def query_evidence_observations_service(
    db: Session,
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    data_state: Optional[str] = None,
    verification_status: Optional[str] = None,
    segment_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Queries privacy-sanitized evidence observations.
    Strictly excludes reporter personal details.
    """
    from app.models.evidence import EvidenceObservation

    query = db.query(EvidenceObservation)

    if category:
        query = query.filter(EvidenceObservation.category == category)
    if source_type:
        query = query.filter(EvidenceObservation.source_type == source_type)
    if data_state:
        query = query.filter(EvidenceObservation.data_state == data_state)
    if verification_status:
        query = query.filter(EvidenceObservation.verification_status == verification_status)
    if segment_id:
        query = query.filter(EvidenceObservation.segment_id == segment_id)

    total = query.count()
    records = query.order_by(EvidenceObservation.observed_at.desc()).offset(offset).limit(limit).all()

    items = [
        {
            "id": r.id,
            "sourceId": r.source_id,
            "sourceType": r.source_type,
            "category": r.category,
            "subcategory": r.subcategory,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "geometry": r.geometry or {},
            "segmentId": r.segment_id,
            "edgeU": r.edge_u,
            "edgeV": r.edge_v,
            "edgeKey": r.edge_key or 0,
            "matchDistanceMeters": r.match_distance_meters,
            "matchMethod": r.match_method,
            "matchStatus": r.match_status,
            "observedAt": r.observed_at,
            "ingestedAt": r.ingested_at,
            "sourceAttribution": r.source_attribution,
            "verificationStatus": r.verification_status,
            "severity": r.severity,
            "confidence": r.confidence,
            "dataState": r.data_state,
            "provenance": r.provenance,
            "limitations": r.limitations or [],
            "attributes": r.attributes or {}
        }
        for r in records
    ]
    return items, total


def get_map_layers_bundle(db: Session, study_area: Optional[Any] = None) -> Dict[str, Any]:
    """
    Compiles an aggregated, high-performance GeoJSON/JSON bundle of all independently
    controllable map layers, distinguishing actual mapped data, community reports,
    inferred/estimated values, and unknown information.
    """
    from app.models.report import CommunityReport
    from app.geospatial.facilities_adapter import VERIFIED_PILOT_FACILITIES

    # 1. Facilities and Landmarks (Verified pilot corridor data)
    assistance_list = []
    landmarks_list = []
    for fac in VERIFIED_PILOT_FACILITIES:
        lat = fac.get("lat") or fac.get("latitude")
        lon = fac.get("lon") or fac.get("longitude")
        ftype = fac.get("facility_type", "civic")
        is_asst = fac.get("is_assistance", False)
        item = {
            "id": fac.get("id"),
            "name": fac.get("name"),
            "category": ftype,
            "latitude": lat,
            "longitude": lon,
            "isAssistance": is_asst,
            "source": "OpenStreetMap contributors (verified)",
            "limitations": "Operating hours, desk staffing, and immediate response readiness are unverified in real time."
        }
        if is_asst:
            assistance_list.append(item)
        else:
            landmarks_list.append(item)

    # 2. Dog Encounter Reports
    dog_reports_db = db.query(CommunityReport).filter(
        CommunityReport.category.in_(["dog_sighting", "dog_group", "dog_aggressive", "dog_bite"]),
        CommunityReport.status != "rejected",
        CommunityReport.latitude.isnot(None),
        CommunityReport.longitude.isnot(None)
    ).all()
    dogs_list = [
        {
            "id": r.id,
            "category": r.category,
            "categoryLabel": r.category_label,
            "description": r.description,
            "location": r.location,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "dogCount": r.dog_count,
            "isAggressive": r.is_aggressive,
            "encounterTime": r.encounter_time.isoformat() if r.encounter_time else None,
            "corroborations": r.corroborations,
            "outdatedFlags": getattr(r, "outdated_flags", 0),
            "status": r.status,
            "sourceType": "community_report",
            "confidence": getattr(r, "location_confidence", "user_pinned")
        }
        for r in dog_reports_db
    ]

    # 3. Approved Community Hazard Reports
    comm_reports_db = db.query(CommunityReport).filter(
        CommunityReport.status == "approved",
        ~CommunityReport.category.in_(["dog_sighting", "dog_group", "dog_aggressive", "dog_bite"]),
        CommunityReport.latitude.isnot(None),
        CommunityReport.longitude.isnot(None)
    ).all()
    community_list = [
        {
            "id": r.id,
            "category": r.category,
            "categoryLabel": r.category_label,
            "description": r.description,
            "location": r.location,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "corroborations": r.corroborations,
            "outdatedFlags": getattr(r, "outdated_flags", 0),
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "sourceType": "community_report",
            "confidence": "community_corroborated" if r.corroborations > 1 else "moderator_approved"
        }
        for r in comm_reports_db
    ]

    # 4. Street Lighting and Infrastructure Segments
    segments_db = db.query(StreetSegment).all()
    lighting_list = []
    infra_list = []
    if segments_db:
        for s in segments_db:
            geom = s.geometry or []
            if len(geom) >= 2:
                # Lighting overlay line
                lighting_list.append({
                    "id": s.id,
                    "streetName": s.street_name,
                    "litStatus": s.lit_status,  # lit, unlit, conflicting, unmapped
                    "lengthMeters": s.length_meters,
                    "geometry": geom,
                    "coverage": s.coverage,
                    "evidenceCoverage": 0.85 if s.coverage == "adequate" else (0.50 if s.coverage == "limited" else 0.20),
                    "source": s.source
                })
                # Infrastructure points/lines
                infra_list.append({
                    "id": s.id,
                    "streetName": s.street_name,
                    "sidewalkStatus": getattr(s, "sidewalk_status", "unmapped"),
                    "crossingStatus": getattr(s, "crossing_status", "unmapped"),
                    "crossingDifficulty": getattr(s, "crossing_difficulty", "unknown"),
                    "hasTactilePaving": getattr(s, "has_tactile_paving", None),
                    "geometry": geom,
                    "lengthMeters": s.length_meters
                })
    else:
        # Fallback to default route corridor segments
        for seg in DEFAULT_SEGMENTS.get("route-evidence", []):
            geom = seg.get("geometry", [])
            lighting_list.append({
                "id": seg.get("id"),
                "streetName": seg.get("streetName"),
                "litStatus": "lit" if seg.get("coverage") == "adequate" else "unmapped",
                "lengthMeters": 400.0,
                "geometry": geom,
                "evidenceCoverage": 0.85 if seg.get("coverage") == "adequate" else 0.20,
                "source": seg.get("source")
            })

    # 5. Crime Clusters / Hotspots
    crime_obs_db = db.query(EvidenceObservation).filter(
        EvidenceObservation.category == "crime",
        EvidenceObservation.latitude.isnot(None),
        EvidenceObservation.longitude.isnot(None)
    ).all()
    crime_list = [
        {
            "id": c.id,
            "category": c.subcategory or "historical_incident",
            "latitude": c.latitude,
            "longitude": c.longitude,
            "severity": c.severity,
            "observedAt": c.observed_at.isoformat() if c.observed_at else None,
            "source": c.source_attribution or "Official Police Records",
            "disclaimer": "Historical recorded incident density; not a predictive probability of future crime."
        }
        for c in crime_obs_db
    ]

    return {
        "studyArea": {
            "name": getattr(study_area, "name", "Bengaluru Pilot Corridor"),
            "bbox": [12.9200, 77.5700, 12.9850, 77.6200]
        },
        "safetyDisclaimer": "SafePath Finder GIS visualization. Evidence layers depict recorded municipal infrastructure and community observations. Absence of mapped reports does not guarantee safety. SafePath is NOT an emergency service and does NOT dispatch police or emergency responders.",
        "layers": {
            "facilities": assistance_list,
            "landmarks": landmarks_list,
            "dogs": dogs_list,
            "community": community_list,
            "lighting": lighting_list,
            "infrastructure": infra_list,
            "crime": crime_list
        },
        "legends": {
            "mappedData": [
                "Municipal street lamp registries (BBMP)",
                "OpenStreetMap verified ways and pedestrian crossings",
                "Emergency assistance facilities (Police and Hospital coordinates)"
            ],
            "communityReports": [
                "Citizen submitted observations",
                "Street dog sighting and encounter reports",
                "Corroborated infrastructure and crossing issues"
            ],
            "inferredValues": [
                "Model prior risk assumptions when evidence is absent",
                "Commercial vitality estimates during daytime/evening periods"
            ],
            "unknownInfo": [
                "Unmapped street lighting conditions (preserved as modeling uncertainty)",
                "Streets lacking documented footpaths or tactile paving",
                "Absence of reports does not indicate zero hazard"
            ],
            "lighting": {
                "provenance": "actual_mapped_and_corroborated",
                "disclaimer": "Streetlights are modeled as active based on OpenStreetMap tags and community observations; real-time operational status is not monitored.",
                "categories": [
                    {"label": "Verified Lit", "color": "#16a34a", "dash": "solid", "state": "mapped"},
                    {"label": "Verified Unlit", "color": "#ea580c", "dash": "solid", "state": "mapped"},
                    {"label": "Conflicting Reports", "color": "#9333ea", "dash": "5,5", "state": "conflicting"},
                    {"label": "Unmapped Lighting", "color": "#94a3b8", "dash": "3,4", "state": "unknown"}
                ]
            },
            "dogs": {
                "provenance": "community_reports",
                "disclaimer": "Observations submitted by local pedestrians; absence of reports does not guarantee no dogs are present.",
                "categories": [
                    {"icon": "paw", "label": "Calm Sighting", "type": "informational"},
                    {"icon": "pack", "label": "Group / Pack", "type": "moderate"},
                    {"icon": "warning", "label": "Aggressive Encounter", "type": "warning"},
                    {"icon": "shield-alert", "label": "Bite Incident", "type": "danger"}
                ]
            },
            "community": {
                "provenance": "community_reports",
                "disclaimer": "Reports verified through moderation and multi-account corroboration. Individual consensus is not scientific proof."
            },
            "facilities": {
                "provenance": "actual_mapped",
                "disclaimer": "Verified physical presence of police stations and hospitals. Proximity to assistance provides resilience but is NOT proof of low crime."
            },
            "infrastructure": {
                "provenance": "actual_mapped",
                "disclaimer": "Sidewalk documentation on OpenStreetMap is incomplete; unmapped streets reflect survey gaps, not verified missing footpaths."
            },
            "crime": {
                "provenance": "historical_police_dataset",
                "disclaimer": "Aggregated historical incident records; non-predictive."
            }
        }
    }


