"""
SafePath Finder — Civic Safety Facilities Adapter (Police & Healthcare)
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

import osmnx as ox

from app.core.config import settings
from app.geospatial.study_area import StudyArea

logger = logging.getLogger(__name__)


@dataclass
class FacilityPoint:
    """Represents a validated civic safety or emergency facility."""
    id: str
    facility_type: str  # Strictly "police" or "hospital"
    name: str
    latitude: float
    longitude: float
    source: str
    confidence: str  # "verified_spatial_point" or "approximate"
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FacilityAuditResult:
    """Aggregated audit of civic emergency points of interest."""
    study_area_name: str
    police_stations: List[FacilityPoint]
    hospitals: List[FacilityPoint]
    sources: List[str]
    retrieved_at: str
    attribution: str = "© OpenStreetMap contributors, Open Database License (ODbL) 1.0"

    @property
    def police_count(self) -> int:
        return len(self.police_stations)

    @property
    def hospital_count(self) -> int:
        return len(self.hospitals)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "studyAreaName": self.study_area_name,
            "policeCount": self.police_count,
            "hospitalCount": self.hospital_count,
            "policeStations": [p.to_dict() for p in self.police_stations],
            "hospitals": [h.to_dict() for h in self.hospitals],
            "sources": self.sources,
            "retrievedAt": self.retrieved_at,
            "attribution": self.attribution
        }


class BaseFacilityAdapter(ABC):
    """Abstract interface for civic safety facility retrieval."""

    @abstractmethod
    def get_facilities(
        self,
        study_area: StudyArea,
        force_reload: bool = False,
        fetch_live: bool = False
    ) -> FacilityAuditResult:
        """Retrieves and separates police stations and healthcare facilities."""
        pass


class OsmFacilityAdapter(BaseFacilityAdapter):
    """
    Retrieves police and hospital POIs from OpenStreetMap via OSMnx Overpass features API,
    with JSON caching to avoid redundant external network queries.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or settings.GEOSPATIAL_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, study_area: StudyArea) -> str:
        return os.path.join(self.cache_dir, f"facilities_{study_area.slug}.json")

    def get_facilities(
        self,
        study_area: StudyArea,
        force_reload: bool = False,
        fetch_live: bool = False
    ) -> FacilityAuditResult:
        cache_path = self._get_cache_path(study_area)

        # 1. Attempt cache load
        if not force_reload and os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                police = [FacilityPoint(**p) for p in data.get("policeStations", [])]
                hospitals = [FacilityPoint(**h) for h in data.get("hospitals", [])]
                return FacilityAuditResult(
                    study_area_name=study_area.name,
                    police_stations=police,
                    hospitals=hospitals,
                    sources=data.get("sources", ["OpenStreetMap (Cached)"]),
                    retrieved_at=data.get("retrievedAt", datetime.now(timezone.utc).isoformat()),
                    attribution=data.get("attribution", "© OpenStreetMap contributors, ODbL 1.0")
                )
            except Exception as e:
                logger.warning(f"Could not read facility cache {cache_path}: {e}")

        # If live query not explicitly requested and cache is missing, return un-synced audit
        if not fetch_live and not force_reload:
            return FacilityAuditResult(
                study_area_name=study_area.name,
                police_stations=[],
                hospitals=[],
                sources=["OpenStreetMap Overpass (amenity=police, amenity=hospital, amenity=clinic)"],
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                attribution="© OpenStreetMap contributors, ODbL 1.0 (Uncached; set fetch_live=true to sync)"
            )

        # 2. Live query via OSMnx
        police_points: List[FacilityPoint] = []
        hospital_points: List[FacilityPoint] = []
        sources = ["OpenStreetMap Overpass (amenity=police, amenity=hospital, amenity=clinic)"]

        try:
            # Query Police Stations
            police_gdf = ox.features.features_from_bbox(
                bbox=study_area.bbox_osmnx,
                tags={"amenity": ["police"]}
            )
            for idx, row in police_gdf.iterrows():
                geom = row.geometry
                lat, lon = (geom.y, geom.x) if geom.geom_type == "Point" else (geom.centroid.y, geom.centroid.x)
                name = row.get("name") or "Unnamed Police Facility"
                police_points.append(
                    FacilityPoint(
                        id=f"pol-{idx}",
                        facility_type="police",
                        name=str(name),
                        latitude=float(lat),
                        longitude=float(lon),
                        source="OpenStreetMap",
                        confidence="verified_spatial_point" if geom.geom_type == "Point" else "approximate_centroid",
                        metadata={"emergency": row.get("emergency"), "operator": row.get("operator")}
                    )
                )
        except Exception as e:
            logger.info(f"Police query returned empty or failed for {study_area.name}: {e}")

        try:
            # Query Hospitals & Clinics (strictly separate from police)
            hosp_gdf = ox.features.features_from_bbox(
                bbox=study_area.bbox_osmnx,
                tags={"amenity": ["hospital", "clinic"]}
            )
            for idx, row in hosp_gdf.iterrows():
                geom = row.geometry
                lat, lon = (geom.y, geom.x) if geom.geom_type == "Point" else (geom.centroid.y, geom.centroid.x)
                name = row.get("name") or "Unnamed Medical Facility"
                hospital_points.append(
                    FacilityPoint(
                        id=f"med-{idx}",
                        facility_type="hospital",
                        name=str(name),
                        latitude=float(lat),
                        longitude=float(lon),
                        source="OpenStreetMap",
                        confidence="verified_spatial_point" if geom.geom_type == "Point" else "approximate_centroid",
                        metadata={"healthcare": row.get("healthcare"), "emergency": row.get("emergency")}
                    )
                )
        except Exception as e:
            logger.info(f"Healthcare query returned empty or failed for {study_area.name}: {e}")

        result = FacilityAuditResult(
            study_area_name=study_area.name,
            police_stations=police_points,
            hospitals=hospital_points,
            sources=sources,
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )

        # 3. Persist to cache
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to cache facilities to {cache_path}: {e}")

        return result
