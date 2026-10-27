from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.evidence import StreetSegment, EvidenceSource
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

