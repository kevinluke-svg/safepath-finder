"""
SafePath Finder — Geospatial Geocoding & Location Search Service
Integrates OpenStreetMap Nominatim with robust in-memory caching,
local corridor landmark prioritization, and explicit study area boundary checks.
"""

import re
import time
import math
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple

import httpx

from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    InvalidCoordinateError,
    OutOfCoverageError,
    LocationNotFoundError,
    AmbiguousLocationError,
    GeocodingServiceUnavailableError,
)
from app.schemas.geocoding import GeocodingResult, GeocodingSearchResponse

logger = logging.getLogger(__name__)

# Known corridor landmarks within the active Bengaluru Pilot Corridor
# Used for instant offline resolution and autocomplete prioritization
CORRIDOR_LANDMARKS: Dict[str, Dict[str, Any]] = {
    "jayanagar 4th block": {
        "name": "Jayanagar 4th Block",
        "displayName": "Jayanagar 4th Block, Bengaluru, Karnataka, India",
        "latitude": 12.9257,
        "longitude": 77.5833,
        "type": "suburb",
        "address": {"suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    },
    "jayanagar 3rd block": {
        "name": "Jayanagar 3rd Block",
        "displayName": "Jayanagar 3rd Block, 10th Main Road, Bengaluru, Karnataka, India",
        "latitude": 12.9290,
        "longitude": 77.5831,
        "type": "suburb",
        "address": {"suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    },
    "jayanagar": {
        "name": "Jayanagar",
        "displayName": "Jayanagar Commercial Hub, Bengaluru, Karnataka, India",
        "latitude": 12.9257,
        "longitude": 77.5833,
        "type": "suburb",
        "address": {"suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    },
    "south end circle": {
        "name": "South End Circle",
        "displayName": "South End Circle Metro & Junction, Jayanagar, Bengaluru, Karnataka, India",
        "latitude": 12.9330,
        "longitude": 77.5832,
        "type": "transit",
        "address": {"junction": "South End Circle", "suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "south end": {
        "name": "South End Circle",
        "displayName": "South End Circle, Jayanagar, Bengaluru, Karnataka, India",
        "latitude": 12.9330,
        "longitude": 77.5832,
        "type": "transit",
        "address": {"suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "madhavan park": {
        "name": "Madhavan Park",
        "displayName": "Madhavan Park, 10th Main Road, Jayanagar, Bengaluru, Karnataka, India",
        "latitude": 12.9370,
        "longitude": 77.5860,
        "type": "leisure",
        "address": {"park": "Madhavan Park", "suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "ashoka pillar": {
        "name": "Ashoka Pillar",
        "displayName": "Ashoka Pillar Monument & Circle, 1st Block Jayanagar, Bengaluru, Karnataka, India",
        "latitude": 12.9370,
        "longitude": 77.5835,
        "type": "monument",
        "address": {"landmark": "Ashoka Pillar", "suburb": "Jayanagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "lalbagh west gate": {
        "name": "Lalbagh West Gate",
        "displayName": "Lalbagh Botanical Garden (West Gate Entrance), Basavanagudi, Bengaluru, Karnataka, India",
        "latitude": 12.9460,
        "longitude": 77.5844,
        "type": "attraction",
        "address": {"attraction": "Lalbagh Botanical Garden", "suburb": "Basavanagudi", "city": "Bengaluru", "state": "Karnataka"}
    },
    "lalbagh main gate": {
        "name": "Lalbagh Main Gate",
        "displayName": "Lalbagh Botanical Garden (North / Main Gate), Mavalli, Bengaluru, Karnataka, India",
        "latitude": 12.9501,
        "longitude": 77.5847,
        "type": "attraction",
        "address": {"attraction": "Lalbagh Botanical Garden", "suburb": "Mavalli", "city": "Bengaluru", "state": "Karnataka"}
    },
    "lalbagh": {
        "name": "Lalbagh Botanical Garden",
        "displayName": "Lalbagh Botanical Garden, Bengaluru, Karnataka, India",
        "latitude": 12.9501,
        "longitude": 77.5847,
        "type": "park",
        "address": {"attraction": "Lalbagh Botanical Garden", "city": "Bengaluru", "state": "Karnataka"}
    },
    "gandhi bazaar": {
        "name": "Gandhi Bazaar",
        "displayName": "Gandhi Bazaar Main Road, Basavanagudi, Bengaluru, Karnataka, India",
        "latitude": 12.9420,
        "longitude": 77.5720,
        "type": "commercial",
        "address": {"road": "Gandhi Bazaar Main Road", "suburb": "Basavanagudi", "city": "Bengaluru", "state": "Karnataka"}
    },
    "subbaiah circle": {
        "name": "Subbaiah Circle",
        "displayName": "Subbaiah Circle, Lalbagh Road, Shantinagar, Bengaluru, Karnataka, India",
        "latitude": 12.9580,
        "longitude": 77.5860,
        "type": "junction",
        "address": {"junction": "Subbaiah Circle", "suburb": "Shantinagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "corporation circle": {
        "name": "Corporation Circle",
        "displayName": "Corporation Circle (Hudson Circle), Sampangi Rama Nagara, Bengaluru, Karnataka, India",
        "latitude": 12.9680,
        "longitude": 77.5880,
        "type": "junction",
        "address": {"junction": "Corporation Circle", "city": "Bengaluru", "state": "Karnataka"}
    },
    "richmond circle": {
        "name": "Richmond Circle",
        "displayName": "Richmond Circle, General K.S. Thimayya Road, Richmond Town, Bengaluru, Karnataka, India",
        "latitude": 12.9660,
        "longitude": 77.5990,
        "type": "junction",
        "address": {"suburb": "Richmond Town", "city": "Bengaluru", "state": "Karnataka"}
    },
    "cubbon park": {
        "name": "Cubbon Park",
        "displayName": "Cubbon Park (Sri Chamarajendra Park), Kasturba Road, Bengaluru, Karnataka, India",
        "latitude": 12.9770,
        "longitude": 77.5920,
        "type": "park",
        "address": {"park": "Cubbon Park", "city": "Bengaluru", "state": "Karnataka"}
    },
    "mg road": {
        "name": "MG Road",
        "displayName": "Mahatma Gandhi Road (MG Road), Ashok Nagar, Bengaluru, Karnataka, India",
        "latitude": 12.9750,
        "longitude": 77.6050,
        "type": "commercial",
        "address": {"road": "Mahatma Gandhi Road", "suburb": "Ashok Nagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "brigade road": {
        "name": "Brigade Road",
        "displayName": "Brigade Road Commercial Promenade, Ashok Nagar, Bengaluru, Karnataka, India",
        "latitude": 12.9740,
        "longitude": 77.6070,
        "type": "commercial",
        "address": {"road": "Brigade Road", "suburb": "Ashok Nagar", "city": "Bengaluru", "state": "Karnataka"}
    },
    "electronic city": {
        "name": "Electronic City",
        "displayName": "Electronic City, Bengaluru, Bangalore South, Bengaluru Urban, Karnataka, 560100, India",
        "latitude": 12.8436,
        "longitude": 77.6687,
        "type": "suburb",
        "address": {"suburb": "Electronic City", "city": "Bengaluru", "state": "Karnataka", "postcode": "560100", "country": "India"}
    },
    "koramangala": {
        "name": "Koramangala",
        "displayName": "Koramangala, Bengaluru, Bangalore South, Bengaluru Urban, Karnataka, India",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "type": "suburb",
        "address": {"suburb": "Koramangala", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    },
    "indiranagar": {
        "name": "Indiranagar",
        "displayName": "Indiranagar, Bengaluru, Bangalore East, Bengaluru Urban, Karnataka, India",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "type": "suburb",
        "address": {"suburb": "Indiranagar", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    },
    "whitefield": {
        "name": "Whitefield",
        "displayName": "Whitefield, Bengaluru, Bangalore East, Bengaluru Urban, Karnataka, India",
        "latitude": 12.9698,
        "longitude": 77.7499,
        "type": "suburb",
        "address": {"suburb": "Whitefield", "city": "Bengaluru", "state": "Karnataka", "country": "India"}
    }
}


class GeocodingService:
    """
    Manages location search and forward geocoding with:
    - OpenStreetMap Nominatim provider integration
    - In-memory thread-safe TTL request cache
    - Pilot corridor landmark fast-matching
    - Transparent study area coverage evaluation
    - Controlled error states without sensitive credential leakage
    """

    def __init__(self, study_area: Optional[StudyArea] = None):
        self.study_area = study_area or StudyArea.from_settings()
        self._cache: Dict[str, Tuple[float, List[GeocodingResult]]] = {}
        self._cache_lock = threading.Lock()
        self.ttl_seconds = settings.GEOCODING_CACHE_TTL_SECONDS

    def normalize_query(self, query: str) -> str:
        """Normalizes query for case-insensitive, whitespace-agnostic caching."""
        if not query:
            return ""
        clean = re.sub(r"[^\w\s,\.\-]", " ", query.lower()).strip()
        return re.sub(r"\s+", " ", clean)

    def parse_coordinate_query(self, query: str) -> Optional[GeocodingResult]:
        """Detects whether query is a direct latitude, longitude coordinate string."""
        if not query:
            return None
        match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", query.strip())
        if not match:
            return None

        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
        except (ValueError, TypeError):
            return None

        # Validate range
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None

        in_study = self.study_area.contains_point(lat, lon)
        dist = self.study_area.distance_to_boundary_meters(lat, lon)

        return GeocodingResult(
            id=f"coord_{lat:.5f}_{lon:.5f}",
            name=f"{lat:.5f}, {lon:.5f}",
            displayName=f"Explicit Coordinates ({lat:.5f}, {lon:.5f})",
            latitude=lat,
            longitude=lon,
            type="coordinate",
            address={"coordinate": f"{lat:.5f}, {lon:.5f}"},
            inStudyArea=in_study,
            studyAreaDistanceMeters=dist,
            importance=1.0
        )

    def search_local_landmarks(self, norm_query: str, limit: int = 5) -> List[GeocodingResult]:
        """Matches local corridor landmarks to provide instant, offline-capable results."""
        results: List[GeocodingResult] = []
        if not norm_query or len(norm_query) < 2:
            return results

        # 1. Exact or prefix matches
        for key, data in CORRIDOR_LANDMARKS.items():
            if key == norm_query or key.startswith(norm_query) or norm_query in key:
                lat = data["latitude"]
                lon = data["longitude"]
                in_study = self.study_area.contains_point(lat, lon)
                dist = self.study_area.distance_to_boundary_meters(lat, lon)

                # Higher importance for exact prefix
                importance = 0.95 if key == norm_query else 0.85

                results.append(GeocodingResult(
                    id=f"local_{key.replace(' ', '_')}",
                    name=data["name"],
                    displayName=data["displayName"],
                    latitude=lat,
                    longitude=lon,
                    type=data.get("type", "landmark"),
                    address=data.get("address", {}),
                    inStudyArea=in_study,
                    studyAreaDistanceMeters=dist,
                    importance=importance
                ))

            if len(results) >= limit:
                break

        return results

    def _query_upstream_provider(self, query: str, limit: int = 5, near_study_area: bool = True) -> List[GeocodingResult]:
        """Queries the configured upstream geocoding provider (Nominatim)."""
        base_url = settings.GEOCODING_BASE_URL.rstrip("/")
        url = f"{base_url}/search"

        headers = {
            "User-Agent": settings.GEOCODING_USER_AGENT,
            "Accept": "application/json"
        }

        params: Dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": limit
        }

        # If near_study_area, bias towards Karnataka/Bengaluru without strictly restricting
        if near_study_area:
            # Greater Bengaluru bounding box: [west, north, east, south] in Nominatim viewbox format
            params["viewbox"] = "77.40,13.15,77.80,12.75"
            params["bounded"] = 0

        if settings.GEOCODING_API_KEY:
            params["key"] = settings.GEOCODING_API_KEY

        try:
            with httpx.Client(timeout=settings.GEOCODING_TIMEOUT_SECONDS) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 429:
                    logger.warning("Upstream geocoding provider rate-limited (HTTP 429).")
                    raise GeocodingServiceUnavailableError("Geocoding service rate-limited. Please try again in a few moments.")
                if resp.status_code >= 500:
                    logger.warning(f"Upstream geocoding provider error ({resp.status_code}).")
                    raise GeocodingServiceUnavailableError("Geocoding provider temporarily unavailable.")

                resp.raise_for_status()
                data = resp.json()

        except httpx.TimeoutException:
            logger.warning(f"Geocoding request timed out for query '{query}'.")
            raise GeocodingServiceUnavailableError("Geocoding request timed out. Please try again.")
        except httpx.RequestError as e:
            logger.warning(f"Geocoding network error: {e}")
            raise GeocodingServiceUnavailableError("Geocoding network connection unavailable.")
        except Exception as e:
            if isinstance(e, GeocodingServiceUnavailableError):
                raise
            logger.warning(f"Unexpected geocoding exception: {e}")
            raise GeocodingServiceUnavailableError(f"Geocoding service encountered an error: {str(e)}")

        results: List[GeocodingResult] = []
        if not isinstance(data, list):
            return results

        for item in data:
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, ValueError, TypeError):
                continue

            # Extract name and display components
            display_name = item.get("display_name", "")
            name = item.get("name")
            if not name:
                name = display_name.split(",")[0].strip() if display_name else "Location"

            address = item.get("address", {})
            place_type = item.get("type") or item.get("category") or "place"
            in_study = self.study_area.contains_point(lat, lon)
            dist = self.study_area.distance_to_boundary_meters(lat, lon)
            importance = float(item.get("importance", 0.5))

            bbox = None
            if "boundingbox" in item and len(item["boundingbox"]) == 4:
                try:
                    bbox = [float(x) for x in item["boundingbox"]]
                except (ValueError, TypeError):
                    bbox = None

            results.append(GeocodingResult(
                id=str(item.get("place_id") or f"osm_{item.get('osm_id', 'unknown')}"),
                name=name,
                displayName=display_name,
                latitude=lat,
                longitude=lon,
                type=place_type,
                address=address,
                inStudyArea=in_study,
                studyAreaDistanceMeters=dist,
                importance=importance,
                boundingBox=bbox
            ))

        return results

    def search(self, query: str, limit: int = 5, near_study_area: bool = True) -> List[GeocodingResult]:
        """
        Searches for locations matching the user query:
        1. Checks for coordinate string ("12.9257, 77.5833")
        2. Checks in-memory TTL cache
        3. Queries local corridor landmarks
        4. Queries upstream provider (Nominatim)
        5. Merges, deduplicates, and caches results
        """
        if not query or len(query.strip()) < 2:
            return []

        # 1. Coordinate check
        coord_match = self.parse_coordinate_query(query)
        if coord_match:
            return [coord_match]

        norm_query = self.normalize_query(query)

        # 2. Cache lookup
        now = time.time()
        with self._cache_lock:
            if norm_query in self._cache:
                timestamp, cached_results = self._cache[norm_query]
                if (now - timestamp) < self.ttl_seconds:
                    return cached_results[:limit]

        # 3. Local landmark lookup
        local_matches = self.search_local_landmarks(norm_query, limit=limit)

        # 4. Upstream query
        upstream_results: List[GeocodingResult] = []
        upstream_error = None
        try:
            upstream_results = self._query_upstream_provider(query, limit=limit, near_study_area=near_study_area)
        except GeocodingServiceUnavailableError as e:
            upstream_error = e

        # 5. Merge and deduplicate
        combined: List[GeocodingResult] = []
        seen_coords = set()

        # Prioritize local matches that are exact/prefix
        for r in local_matches:
            coord_key = (round(r.latitude, 4), round(r.longitude, 4))
            seen_coords.add(coord_key)
            combined.append(r)

        for r in upstream_results:
            coord_key = (round(r.latitude, 4), round(r.longitude, 4))
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                combined.append(r)

        # Sort: prefer in-study-area, then by importance
        combined.sort(key=lambda x: (x.inStudyArea, x.importance or 0.0), reverse=True)
        final_results = combined[:limit]

        # If upstream failed and we had zero local matches, re-raise the service unavailable error
        if not final_results and upstream_error is not None:
            raise upstream_error

        # Cache results if successful
        with self._cache_lock:
            self._cache[norm_query] = (now, final_results)

        return final_results

    def resolve_location_sync(self, query: str) -> Optional[Tuple[float, float, str, bool]]:
        """
        Synchronously resolves a location query to (latitude, longitude, display_name, in_study_area).
        Used by routing_service to resolve textual origin/destination.
        """
        if not query or not query.strip():
            return None

        # 1. Direct coordinates
        coord = self.parse_coordinate_query(query)
        if coord:
            return (coord.latitude, coord.longitude, coord.displayName, coord.inStudyArea)

        norm_query = self.normalize_query(query)

        # 2. Local exact landmark match
        if norm_query in CORRIDOR_LANDMARKS:
            data = CORRIDOR_LANDMARKS[norm_query]
            lat = data["latitude"]
            lon = data["longitude"]
            in_study = self.study_area.contains_point(lat, lon)
            return (lat, lon, data["displayName"], in_study)

        # 3. Search via geocoder (local + upstream)
        try:
            results = self.search(query, limit=1)
            if results:
                top = results[0]
                return (top.latitude, top.longitude, top.displayName, top.inStudyArea)
            return None
        except GeocodingServiceUnavailableError:
            # Check if any partial local match exists
            local = self.search_local_landmarks(norm_query, limit=1)
            if local:
                top = local[0]
                return (top.latitude, top.longitude, top.displayName, top.inStudyArea)
            raise


# Global singleton instance
_geocoding_service_instance: Optional[GeocodingService] = None

def get_geocoding_service() -> GeocodingService:
    global _geocoding_service_instance
    if _geocoding_service_instance is None:
        _geocoding_service_instance = GeocodingService()
    return _geocoding_service_instance
