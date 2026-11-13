from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session
from app.schemas.route import RouteCompareRequest, RouteCompareResponse
from app.services.routing_service import compare_routes_service
from app.api.deps import get_db
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    OutOfCoverageError,
    InvalidCoordinateError,
    DisconnectedNetworkError,
    LocationNotFoundError,
    AmbiguousLocationError,
    GeocodingServiceUnavailableError,
)
from app.geospatial.network_adapter import OsmNetworkAdapter
from app.geospatial.lighting_adapter import OsmLightingAdapter
from app.geospatial.facilities_adapter import OsmFacilityAdapter
from app.geospatial.crime_adapter import CsvCrimeAdapter
from app.geospatial.community_adapter import DatabaseCommunityAdapter

router = APIRouter(prefix="", tags=["Journeys & Route Comparison"])


@router.post("/routes/compare", response_model=RouteCompareResponse)
def compare_routes(
    payload: RouteCompareRequest,
    db: Session = Depends(get_db)
) -> RouteCompareResponse:
    """
    Compare walking route alternatives with transparent evidence indicators.
    Does not issue unconditional safety guarantees or mask missing data.
    Validates origin and destination coordinates against the active study area boundary.
    Supports departure period (daytime, evening, night) and step-free accessibility constraints.
    """
    try:
        return compare_routes_service(
            origin=payload.origin,
            destination=payload.destination,
            walking_mode=payload.walkingMode,
            preferences=payload.preferences,
            origin_coordinates=payload.originCoordinates,
            destination_coordinates=payload.destinationCoordinates,
            departure_period=payload.departurePeriod,
            step_free=payload.stepFree,
            db=db
        )
    except OutOfCoverageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DisconnectedNetworkError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except GeocodingServiceUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except (InvalidCoordinateError, LocationNotFoundError, AmbiguousLocationError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )



@router.get("/study-area")
def get_study_area_info():
    """Returns active research study area configuration and validated bounding box."""
    study_area = StudyArea.from_settings()
    return study_area.to_dict()


@router.get("/study-area/audit")
def run_data_readiness_audit(db: Session = Depends(get_db)):
    """
    Audits the real evidence sources currently accessible to the SafePath platform:
    pedestrian network cache, lighting coverage, police & healthcare facilities,
    crime dataset availability, and community reports.
    """
    study_area = StudyArea.from_settings()

    # 1. Street Network Audit (from cache or fast inspection)
    net_adapter = OsmNetworkAdapter()
    net_info = {}
    try:
        # Load from cache if present
        graph_path, meta_path = net_adapter._get_cache_paths(study_area)
        import os
        has_cache = os.path.isfile(graph_path)
        net_info = {
            "status": "cached" if has_cache else "uncached",
            "cachePath": graph_path if has_cache else None
        }
    except Exception as e:
        net_info = {"status": "error", "error": str(e)}

    # 2. Lighting Audit
    lighting_adapter = OsmLightingAdapter()
    lighting_res = lighting_adapter.audit_lighting(study_area, graph=None)

    # 3. Facilities Audit (Police vs Healthcare)
    facility_adapter = OsmFacilityAdapter()
    fac_res = facility_adapter.get_facilities(study_area)

    # 4. Crime Evidence Audit
    crime_adapter = CsvCrimeAdapter()
    crime_res = crime_adapter.load_crime_dataset()

    # 5. Community Reports Audit
    comm_adapter = DatabaseCommunityAdapter()
    comm_res = comm_adapter.audit_community_reports(db, study_area)

    # 6. Dog Encounters Evidence Audit
    dog_reports_total = sum(1 for r in comm_res.incidents if (r.category or "").startswith("dog_"))
    dog_audit = {
        "source": "SafePath Citizen Reporting & Moderation Pipeline",
        "externalLiveFeedAvailable": False,
        "externalLiveFeedNotes": (
            "No public municipal real-time GIS stream or live API is currently operated by BBMP Animal Husbandry / "
            "Animal Birth Control (ABC) for street dog sightings. OpenStreetMap lacks dynamic stray animal observations. "
            "Citizen-reported evidence with 4-state moderation is the sole empirical source."
        ),
        "totalDogReports": dog_reports_total,
        "approvedDogReports": sum(1 for r in comm_res.incidents if (r.category or "").startswith("dog_") and r.status == "approved"),
        "pendingDogReports": sum(1 for r in comm_res.incidents if (r.category or "").startswith("dog_") and r.status == "pending"),
        "flaggedDogReports": sum(1 for r in comm_res.incidents if (r.category or "").startswith("dog_") and r.status == "flagged"),
        "categories": {
            "dog_sighting": sum(1 for r in comm_res.incidents if r.category == "dog_sighting"),
            "dog_group": sum(1 for r in comm_res.incidents if r.category == "dog_group"),
            "dog_aggressive": sum(1 for r in comm_res.incidents if r.category == "dog_aggressive"),
            "dog_bite": sum(1 for r in comm_res.incidents if r.category == "dog_bite"),
        },
        "epistemologicalPolicy": (
            "Absence of reported sightings is NEVER interpreted as absence of dogs. Ordinary sightings remain purely "
            "informational and do not inflate street risk. Aggressive encounters contribute to safety-prioritized "
            "penalties with recency decay."
        )
    }

    # 7. Pedestrian Infrastructure Audit
    from app.models.evidence import StreetSegment
    total_db_segs = db.query(StreetSegment).count()
    if total_db_segs > 0:
        doc_sw = db.query(StreetSegment).filter(StreetSegment.sidewalk_status.in_(["both", "left", "right", "separate"])).count()
        unmapped_sw = db.query(StreetSegment).filter(StreetSegment.sidewalk_status == "unmapped").count()
        absent_sw = db.query(StreetSegment).filter(StreetSegment.sidewalk_status == "none").count()
        tactile_cnt = db.query(StreetSegment).filter(StreetSegment.has_tactile_paving == True).count()
        high_diff = db.query(StreetSegment).filter(StreetSegment.crossing_difficulty == "high").count()
        infra_audit = {
            "source": "OpenStreetMap Pedestrian Way & Node Tags",
            "totalSegmentsInspected": total_db_segs,
            "documentedSidewalkCount": doc_sw,
            "documentedSidewalkPercentage": round(doc_sw / total_db_segs * 100.0, 1),
            "unmappedSidewalkCount": unmapped_sw,
            "unmappedSidewalkPercentage": round(unmapped_sw / total_db_segs * 100.0, 1),
            "absentSidewalkCount": absent_sw,
            "tactilePavingCount": tactile_cnt,
            "highDifficultyCrossingsCount": high_diff,
            "epistemologicalPolicy": "Unmapped sidewalk tags indicate survey gaps on OpenStreetMap and are NEVER interpreted as physical absence of footpath."
        }
    else:
        infra_audit = {
            "source": "OpenStreetMap Pedestrian Way & Node Tags",
            "totalSegmentsInspected": 0,
            "documentedSidewalkCount": 0,
            "documentedSidewalkPercentage": 0.0,
            "unmappedSidewalkCount": 0,
            "unmappedSidewalkPercentage": 100.0,
            "absentSidewalkCount": 0,
            "tactilePavingCount": 0,
            "highDifficultyCrossingsCount": 0,
            "epistemologicalPolicy": "Unmapped sidewalk tags indicate survey gaps on OpenStreetMap and are NEVER interpreted as physical absence of footpath."
        }

    return {
        "studyArea": study_area.to_dict(),
        "network": net_info,
        "lighting": lighting_res.to_dict(),
        "facilities": fac_res.to_dict(),
        "pedestrianInfrastructure": infra_audit,
        "crime": crime_res.to_dict(),
        "communityReports": comm_res.to_dict(),
        "dogEncounters": dog_audit
    }


@router.get("/routes/sensitivity-analysis")
def run_routing_sensitivity_analysis():
    """
    Executes reproducible sensitivity evaluation across:
    - Risk aversion multiplier lambda in [0.0, 5.0]
    - Departure period (daytime, evening, night) lighting modulation
    - Dog encounter evidence differentiation (calm vs aggressive)
    - Pedestrian infrastructure & step-free constraints
    - Epistemological neutral prior R_unknown in [0.20, 0.80] under varying coverage
    """
    from app.geospatial.sensitivity_analysis import SensitivityEvaluator
    evaluator = SensitivityEvaluator()
    return evaluator.run_comprehensive_sensitivity_suite()


