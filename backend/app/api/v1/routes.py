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
    """
    try:
        return compare_routes_service(
            origin=payload.origin,
            destination=payload.destination,
            walking_mode=payload.walkingMode,
            preferences=payload.preferences,
            origin_coordinates=payload.originCoordinates,
            destination_coordinates=payload.destinationCoordinates,
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

    return {
        "studyArea": study_area.to_dict(),
        "network": net_info,
        "lighting": lighting_res.to_dict(),
        "facilities": fac_res.to_dict(),
        "crime": crime_res.to_dict(),
        "communityReports": comm_res.to_dict()
    }

