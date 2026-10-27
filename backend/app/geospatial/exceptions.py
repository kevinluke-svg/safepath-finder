"""
SafePath Finder — Geospatial & Data Adapter Exceptions
"""

class GeospatialError(Exception):
    """Base exception for all geospatial and routing errors."""
    pass


class InvalidCoordinateError(GeospatialError):
    """Raised when coordinates fall outside valid mathematical WGS-84 ranges [-90..90, -180..180]."""
    pass


class OutOfCoverageError(GeospatialError):
    """Raised when origin, destination, or waypoint falls outside the configured study area."""
    pass


class InvalidStudyAreaError(GeospatialError):
    """Raised when a study area definition has invalid bounding box limits or missing name."""
    pass


class NetworkRetrievalError(GeospatialError):
    """Raised when the pedestrian street network cannot be retrieved or loaded from cache."""
    pass


class DisconnectedNetworkError(GeospatialError):
    """Raised when origin and destination reside in disconnected network subgraphs."""
    pass


class DatasetNotFoundError(GeospatialError):
    """Raised when an expected real dataset (e.g., crime CSV) is missing."""
    pass


class DataQualityError(GeospatialError):
    """Raised when imported data fails validation or violates privacy/formatting rules."""
    pass


class GeocodingError(GeospatialError):
    """Base exception for geocoding and location resolution failures."""
    pass


class LocationNotFoundError(InvalidCoordinateError, GeocodingError):
    """Raised when geocoding service yields no matching places for a query."""
    pass


class AmbiguousLocationError(GeocodingError):
    """Raised when multiple distinct locations match a query and disambiguation is required."""
    pass


class GeocodingServiceUnavailableError(GeocodingError):
    """Raised when the upstream geocoding provider fails, times out, or cannot be reached."""
    pass
