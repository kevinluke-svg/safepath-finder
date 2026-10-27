"""
SafePath Finder — Configurable Study Area & Boundary Validation
"""

import re
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from app.core.config import settings
from app.geospatial.exceptions import (
    InvalidCoordinateError,
    OutOfCoverageError,
    InvalidStudyAreaError,
)


@dataclass(frozen=True)
class StudyArea:
    """
    Represents an explicit, validated geographical boundary for pedestrian routing
    and evidence data collection.
    """
    name: str
    south: float
    west: float
    north: float
    east: float
    place_name: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidStudyAreaError("Study area name cannot be empty.")

        # Coordinate domain validations
        if not (-90.0 <= self.south <= 90.0):
            raise InvalidStudyAreaError(f"South latitude ({self.south}) must be between -90 and 90 degrees.")
        if not (-90.0 <= self.north <= 90.0):
            raise InvalidStudyAreaError(f"North latitude ({self.north}) must be between -90 and 90 degrees.")
        if not (-180.0 <= self.west <= 180.0):
            raise InvalidStudyAreaError(f"West longitude ({self.west}) must be between -180 and 180 degrees.")
        if not (-180.0 <= self.east <= 180.0):
            raise InvalidStudyAreaError(f"East longitude ({self.east}) must be between -180 and 180 degrees.")

        # Relational bbox validations
        if self.south >= self.north:
            raise InvalidStudyAreaError(
                f"South latitude ({self.south}) must be strictly less than North latitude ({self.north})."
            )
        if self.west >= self.east:
            raise InvalidStudyAreaError(
                f"West longitude ({self.west}) must be strictly less than East longitude ({self.east})."
            )

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Returns standard (south, west, north, east) tuple."""
        return (self.south, self.west, self.north, self.east)

    @property
    def bbox_osmnx(self) -> Tuple[float, float, float, float]:
        """
        Returns bounding box tuple in OSMnx 2.x order: (left, bottom, right, top)
        which corresponds to (west, south, east, north).
        """
        return (self.west, self.south, self.east, self.north)

    @property
    def slug(self) -> str:
        """Generates a stable, filesystem-safe identifier for caching."""
        clean_name = re.sub(r"[^a-zA-Z0-9]+", "_", self.name.strip().lower()).strip("_")
        return f"{clean_name}_{self.south:.4f}_{self.west:.4f}_{self.north:.4f}_{self.east:.4f}".replace(".", "p")

    def contains_point(self, lat: float, lon: float) -> bool:
        """Returns True if point is within the bounding box (inclusive)."""
        return (self.south <= lat <= self.north) and (self.west <= lon <= self.east)

    def distance_to_boundary_meters(self, lat: float, lon: float) -> float:
        """
        Returns geodesic distance in meters from (lat, lon) to the closest point
        on the study area bounding box. Returns 0.0 if the point is inside.
        """
        if self.contains_point(lat, lon):
            return 0.0
        import math
        clamped_lat = max(self.south, min(self.north, lat))
        clamped_lon = max(self.west, min(self.east, lon))

        # Haversine distance
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat)
        phi2 = math.radians(clamped_lat)
        delta_phi = math.radians(clamped_lat - lat)
        delta_lambda = math.radians(clamped_lon - lon)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round(r * c, 1)

    def validate_coordinate_pair(self, lat: float, lon: float, label: str = "Coordinate") -> None:
        """
        Validates coordinate mathematical ranges and verifies membership within study area.
        Raises InvalidCoordinateError or OutOfCoverageError on failure.
        """
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise InvalidCoordinateError(f"{label} latitude and longitude must be numeric values.")

        if not (-90.0 <= lat <= 90.0):
            raise InvalidCoordinateError(f"{label} latitude ({lat}) is outside valid range [-90..90].")
        if not (-180.0 <= lon <= 180.0):
            raise InvalidCoordinateError(f"{label} longitude ({lon}) is outside valid range [-180..180].")

        if not self.contains_point(lat, lon):
            raise OutOfCoverageError(
                f"{label} ({lat:.5f}, {lon:.5f}) is outside configured study area '{self.name}' "
                f"[S: {self.south}, W: {self.west}, N: {self.north}, E: {self.east}]. "
                "Routing requests outside configured coverage cannot be processed without fabricating paths."
            )

    def validate_route_endpoints(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float
    ) -> None:
        """Validates both origin and destination endpoints against study area boundary."""
        self.validate_coordinate_pair(origin_lat, origin_lon, label="Origin")
        self.validate_coordinate_pair(dest_lat, dest_lon, label="Destination")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes study area metadata."""
        return {
            "name": self.name,
            "placeName": self.place_name,
            "description": self.description,
            "bbox": {
                "south": self.south,
                "west": self.west,
                "north": self.north,
                "east": self.east
            },
            "slug": self.slug
        }

    @classmethod
    def from_settings(cls) -> "StudyArea":
        """Constructs active StudyArea from application settings."""
        return cls(
            name=settings.STUDY_AREA_NAME,
            south=settings.STUDY_AREA_BBOX_SOUTH,
            west=settings.STUDY_AREA_BBOX_WEST,
            north=settings.STUDY_AREA_BBOX_NORTH,
            east=settings.STUDY_AREA_BBOX_EAST,
            place_name=settings.STUDY_AREA_PLACE_NAME,
            description="Active research corridor for SafePath Finder"
        )
