import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.schemas.route import (
    RouteCompareResponse,
    RouteAlternative,
    EvidenceSummary,
    StreetlightEvidenceSummary,
    NearbyPlace
)
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    OutOfCoverageError,
    InvalidCoordinateError,
    DisconnectedNetworkError,
    LocationNotFoundError,
    GeocodingServiceUnavailableError,
    NetworkRetrievalError,
)
from app.geospatial.network_adapter import OsmNetworkAdapter
from app.geospatial.facilities_adapter import OsmFacilityAdapter
from app.geospatial.crime_adapter import CsvCrimeAdapter
from app.geospatial.community_adapter import DatabaseCommunityAdapter
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute
from app.services.geocoding_service import get_geocoding_service

logger = logging.getLogger(__name__)

# Known pilot corridor landmarks for text-based origin / destination resolution
KNOWN_LANDMARKS: Dict[str, Tuple[float, float]] = {
    "jayanagar": (12.9257, 77.5833),
    "jayanagar 4th block": (12.9257, 77.5833),
    "jayanagar 3rd block": (12.9290, 77.5831),
    "south end": (12.9330, 77.5832),
    "south end circle": (12.9330, 77.5832),
    "madhavan park": (12.9370, 77.5860),
    "ashoka pillar": (12.9370, 77.5835),
    "ashoka pillar circle": (12.9370, 77.5835),
    "siddapura cross": (12.9415, 77.5840),
    "lalbagh": (12.9501, 77.5847),
    "lalbagh west gate": (12.9460, 77.5844),
    "lalbagh main gate": (12.9501, 77.5847),
    "lalbagh east gate": (12.9501, 77.5885),
    "gandhi bazaar": (12.9420, 77.5720),
    "gandhi bazaar main road": (12.9420, 77.5720),
    "subbaiah circle": (12.9580, 77.5860),
    "shantinagar": (12.9580, 77.5860),
    "corporation circle": (12.9680, 77.5880),
    "richmond circle": (12.9660, 77.5990),
    "cubbon park": (12.9770, 77.5920),
    "kanteerava": (12.9730, 77.5930),
    "mg road": (12.9750, 77.6050),
    "brigade road": (12.9740, 77.6070),
    "residency road": (12.9700, 77.6040),
}


def _parse_coordinate_pair(val: Any) -> Optional[Tuple[float, float]]:
    """Attempts to extract (latitude, longitude) from a list/tuple or 'lat, lon' string."""
    if isinstance(val, (list, tuple)) and len(val) == 2:
        try:
            return float(val[0]), float(val[1])
        except (ValueError, TypeError):
            return None
    if isinstance(val, str):
        match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", val.strip())
        if match:
            try:
                return float(match.group(1)), float(match.group(2))
            except (ValueError, TypeError):
                return None
    return None


def _resolve_landmark_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """Resolves common landmark names within the pilot study area to coordinates."""
    if not text:
        return None
    clean = text.lower().strip()
    # Sort by length descending so specific landmarks ('jayanagar 3rd block') match before broad ones ('jayanagar')
    for name in sorted(KNOWN_LANDMARKS.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, clean):
            return KNOWN_LANDMARKS[name]
    return None


def _resolve_location_robust(
    text: str,
    explicit_coords: Optional[List[float]] = None,
    label: str = "Location"
) -> Tuple[float, float]:
    """
    Resolves a location using:
    1. Explicit numeric coordinates
    2. Coordinate string in text (e.g. '12.9257, 77.5833')
    3. Fast local landmark lookup
    4. GeocodingService (Nominatim with caching)
    Raises LocationNotFoundError or GeocodingServiceUnavailableError on failure.
    """
    coords = (
        _parse_coordinate_pair(explicit_coords)
        or _parse_coordinate_pair(text)
        or _resolve_landmark_coordinates(text)
    )
    if coords is not None:
        return coords

    # Fallback to geocoding service
    try:
        geo = get_geocoding_service()
        resolved = geo.resolve_location_sync(text)
        if resolved:
            return (resolved[0], resolved[1])
    except GeocodingServiceUnavailableError:
        raise
    except Exception as e:
        logger.warning(f"Geocoding exception for '{text}': {e}")
        raise GeocodingServiceUnavailableError(f"Geocoding service unavailable while resolving {label.lower()} '{text}'.")

    raise LocationNotFoundError(
        f"Could not resolve {label} '{text}'. Please check spelling, enter a landmark or street address, or provide explicit coordinates (lat, lon)."
    )


# Module-level router cache to achieve <80ms routing for custom locations
_ROUTER_CACHE: Dict[Tuple, DijkstraRouter] = {}


def compare_routes_service(
    origin: str,
    destination: str,
    walking_mode: str = "pedestrian",
    preferences: Dict[str, Any] = None,
    origin_coordinates: Optional[List[float]] = None,
    destination_coordinates: Optional[List[float]] = None,
    db: Optional[Session] = None
) -> RouteCompareResponse:
    """Compare walking routes and provide explainable multi-attribute scoring without black-box scores."""
    study_area = StudyArea.from_settings()
    prefs = preferences or {}

    # 1. Resolve and validate coordinates
    orig_coords = _resolve_location_robust(origin, origin_coordinates, label="starting location")
    dest_coords = _resolve_location_robust(destination, destination_coordinates, label="destination")

    # Validate against study area boundary
    study_area.validate_coordinate_pair(orig_coords[0], orig_coords[1], label=f"Origin '{origin}'")
    study_area.validate_coordinate_pair(dest_coords[0], dest_coords[1], label=f"Destination '{destination}'")

    # 2. Load genuine pedestrian network graph
    net_adapter = OsmNetworkAdapter()
    try:
        net_result = net_adapter.get_pedestrian_network(study_area)
        graph = net_result.graph
    except Exception as e:
        logger.error(f"Failed to load genuine pedestrian network via adapter: {e}")
        raise NetworkRetrievalError(
            f"Genuine OpenStreetMap pedestrian network for '{study_area.name}' could not be loaded: {str(e)}. "
            "SafePath Finder does not use synthetic or approximated networks for production routing."
        ) from e

    # 3. Load evidence sources
    fac_res = None
    try:
        fac_adapter = OsmFacilityAdapter()
        fac_res = fac_adapter.get_facilities(study_area)
    except Exception as e:
        logger.warning(f"Could not load facilities: {e}")

    crime_res = None
    try:
        crime_adapter = CsvCrimeAdapter()
        crime_res = crime_adapter.load_crime_dataset()
    except Exception as e:
        logger.warning(f"Could not load crime dataset: {e}")

    comm_reports = []
    if db is not None:
        try:
            comm_adapter = DatabaseCommunityAdapter()
            comm_res = comm_adapter.audit_community_reports(db, study_area)
            comm_reports = getattr(comm_res, "records", [])
        except Exception as e:
            logger.warning(f"Could not load community reports from db: {e}")

    # 4. Configure Risk Model with research parameters and user overrides
    risk_model = SegmentRiskModel(
        walking_speed_mps=prefs.get("walkingSpeedMps"),
        lambda_balanced=prefs.get("lambdaBalanced"),
        lambda_safety=prefs.get("lambdaSafety"),
        r_unknown_prior=prefs.get("rUnknownPrior"),
        weight_crime=prefs.get("weightCrime"),
        weight_lighting=prefs.get("weightLighting"),
        weight_community=prefs.get("weightCommunity"),
        weight_assistance=prefs.get("weightAssistance"),
        min_coverage_threshold=prefs.get("minCoverageThreshold")
    )

    # 5. Initialize Dijkstra & Yen Router with in-memory caching for sub-80ms custom routing
    router_cache_key = (
        study_area.slug,
        id(graph),
        risk_model.walking_speed_mps,
        risk_model.lambda_balanced,
        risk_model.lambda_safety,
        risk_model.r_unknown_prior,
        round(risk_model.w_crime, 4),
        round(risk_model.w_lighting, 4),
        round(risk_model.w_community, 4),
        round(risk_model.w_assistance, 4),
        prefs.get("maxDetourRatio"),
        prefs.get("overlapThreshold"),
        prefs.get("maxAlternatives"),
        len(comm_reports)
    )

    if router_cache_key in _ROUTER_CACHE:
        router = _ROUTER_CACHE[router_cache_key]
    else:
        router = DijkstraRouter(
            graph=graph,
            risk_model=risk_model,
            facilities_result=fac_res,
            crime_dataset=crime_res,
            community_reports=comm_reports,
            max_detour_ratio=prefs.get("maxDetourRatio"),
            overlap_threshold=prefs.get("overlapThreshold"),
            max_alternatives=prefs.get("maxAlternatives")
        )
        _ROUTER_CACHE[router_cache_key] = router

    # 6. Determine ranking mode
    prefer_lighting = prefs.get("preferLighting", True)
    avoid_unknown = prefs.get("avoidUnknown", True)
    if prefer_lighting and avoid_unknown:
        ranking_pref = "safety"
        ranking_reason = "Evidence-led Route ranks #1 because lighting verification and low tolerance for unmapped segments are prioritized."
    elif not prefer_lighting and not avoid_unknown:
        ranking_pref = "fastest"
        ranking_reason = "Shortest Sample Route ranks #1 because travel time is prioritized over evidence availability."
    else:
        ranking_pref = "balanced"
        ranking_reason = "Balanced Sample Route ranks well as a compromise between travel distance and evidence coverage."

    # 7. Compute all routes
    include_alts = bool(
        prefs.get("includeAlternatives", False)
        or prefs.get("alternatives", False)
        or (prefs.get("maxAlternatives", 0) > 0)
    )
    computed_routes = router.compute_all_routes(
        origin_lat=orig_coords[0],
        origin_lon=orig_coords[1],
        dest_lat=dest_coords[0],
        dest_lon=dest_coords[1],
        ranking_preference=ranking_pref,
        include_alternatives=include_alts
    )

    # 8. Assemble response
    routes_output: List[RouteAlternative] = []
    for r in computed_routes:
        if r.evidence_coverage >= 0.70:
            cov_label = "adequate"
            fresh_label = "fresh"
        elif r.evidence_coverage >= 0.30:
            cov_label = "limited"
            fresh_label = "fresh" if r.lit_percentage > 0 else "stale"
        else:
            cov_label = "insufficient"
            fresh_label = "stale"

        st_summary = None
        if r.streetlight_summary:
            st_summary = StreetlightEvidenceSummary(**r.streetlight_summary)

        nearby_places = []
        if r.nearby_places:
            nearby_places = [NearbyPlace(**p) for p in r.nearby_places]

        routes_output.append(
            RouteAlternative(
                id=r.id,
                name=r.name,
                category=r.category,
                preference=r.preference,
                distanceMeters=r.distance_meters,
                durationSeconds=r.duration_seconds,
                characteristics=r.characteristics,
                evidenceSummary=EvidenceSummary(
                    coverage=cov_label,
                    coveragePercentage=int(round(r.evidence_coverage * 100)),
                    freshestObservationDays=8 if r.lit_percentage > 0 else 30,
                    freshnessState=fresh_label,
                    riskEstimate=f"Route effective risk: {r.route_risk_indicator:.2f} (composite scale 0-1)",
                    crimeCount=r.crime_incidents_total,
                    lightingCoveragePercentage=r.lit_percentage,
                    feedbackCount=r.community_reports_total,
                    nearestHospitalDistanceMeters=r.min_hospital_distance_meters,
                    nearestPoliceDistanceMeters=r.min_police_distance_meters,
                    dataQualitySummary=f"{round(r.evidence_coverage * 100, 1)}% evidence coverage across indicators"
                ),
                explanation=r.ranking_explanation,
                tradeoffs=r.tradeoffs,
                geometry=r.geometry,
                segments=r.segments,
                routeRisk=r.route_risk_indicator,
                generalizedCost=r.total_cost,
                evidenceCoverage=r.evidence_coverage,
                hasInsufficientEvidence=r.has_insufficient_evidence,
                rankingFactors=r.ranking_factors,
                limitations=r.limitations,
                sourceMetadata=r.source_metadata,
                isIdenticalToFastest=r.is_identical_to_fastest,
                identicalNotes=r.identical_notes,
                streetlightSummary=st_summary,
                nearbyPlaces=nearby_places
            )
        )

    return RouteCompareResponse(
        origin=origin,
        destination=destination,
        walkingMode=walking_mode,
        timestamp=datetime.now(timezone.utc),
        rankingReason=ranking_reason,
        routes=routes_output,
        studyArea=study_area.to_dict()
    )

