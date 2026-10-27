"""
SafePath Finder — Geocoding & Place Autocomplete API Endpoints
"""

from fastapi import APIRouter, Query, HTTPException, status
from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    GeocodingServiceUnavailableError,
    LocationNotFoundError,
)
from app.schemas.geocoding import GeocodingSearchResponse
from app.services.geocoding_service import get_geocoding_service

router = APIRouter(prefix="", tags=["Geocoding & Location Search"])


@router.get("/geocoding/search", response_model=GeocodingSearchResponse)
def search_places(
    q: str = Query(..., min_length=2, max_length=255, description="Search query for street address, landmark, or coordinates"),
    limit: int = Query(5, ge=1, le=10, description="Maximum suggestions to return"),
    near_study_area: bool = Query(True, description="Prioritize research corridor / city region")
) -> GeocodingSearchResponse:
    """
    Search for places, street addresses, and landmarks via geocoding.
    Returns structured suggestions with locality, city, region, coordinates,
    and explicit annotation of whether the location falls within the active
    pedestrian routing network boundary.
    """
    service = get_geocoding_service()
    study_area = StudyArea.from_settings()

    try:
        results = service.search(query=q, limit=limit, near_study_area=near_study_area)
    except GeocodingServiceUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

    return GeocodingSearchResponse(
        query=q,
        provider=settings.GEOCODING_PROVIDER,
        count=len(results),
        results=results,
        studyArea=study_area.to_dict()
    )
