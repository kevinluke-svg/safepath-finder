"""
SafePath Finder — Crime Evidence Adapter & Validated CSV Ingestion Interface
"""

import os
import csv
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import DataQualityError

logger = logging.getLogger(__name__)

# Sensitive column names that must never be ingested into routing evidence
PROHIBITED_PII_COLUMNS = {
    "name", "reporter", "victim", "suspect", "witness", "phone", "mobile",
    "email", "address", "house_number", "aadhaar", "national_id"
}


@dataclass
class CrimeRecord:
    """Represents a validated, privacy-sanitized crime observation or incident."""
    incident_id: str
    category: str
    timestamp: str
    latitude: float
    longitude: float
    spatial_precision: str  # "exact_coordinate", "block_level", "station_aggregated"
    source: str
    is_fixture: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrimeDatasetResult:
    """Summary of audited crime evidence dataset."""
    is_loaded: bool
    record_count: int
    source_name: str
    spatial_precision: str
    licensing: str
    date_range: Optional[Tuple[str, str]]
    categories: List[str]
    limitations: List[str]
    records: List[CrimeRecord]
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "isLoaded": self.is_loaded,
            "recordCount": self.record_count,
            "sourceName": self.source_name,
            "spatialPrecision": self.spatial_precision,
            "licensing": self.licensing,
            "dateRange": self.date_range,
            "categories": self.categories,
            "limitations": self.limitations,
            "filePath": self.file_path,
            "records": [r.to_dict() for r in self.records]
        }


class BaseCrimeAdapter(ABC):
    """Abstract interface for crime evidence ingestion."""

    @abstractmethod
    def load_crime_dataset(self, file_path: Optional[str] = None) -> CrimeDatasetResult:
        """Loads and validates a supplied crime incident dataset."""
        pass

    @abstractmethod
    def get_incidents_in_study_area(
        self,
        study_area: StudyArea,
        file_path: Optional[str] = None
    ) -> List[CrimeRecord]:
        """Returns crime incidents spatialized within study area boundaries."""
        pass


class CsvCrimeAdapter(BaseCrimeAdapter):
    """
    Validated CSV importer for genuine crime incident datasets.
    Rejects PII, validates coordinate boundaries, and reports spatial precision limitations.
    Never fabricates synthetic incidents when data is unavailable.
    """

    def __init__(self, default_file_path: Optional[str] = None):
        self.default_file_path = default_file_path or settings.CRIME_DATA_FILE

    def load_crime_dataset(self, file_path: Optional[str] = None) -> CrimeDatasetResult:
        target_path = file_path or self.default_file_path

        # Honest reporting when no dataset is provided
        if not target_path or not os.path.isfile(target_path):
            return CrimeDatasetResult(
                is_loaded=False,
                record_count=0,
                source_name="None configured",
                spatial_precision="unavailable",
                licensing="N/A",
                date_range=None,
                categories=[],
                limitations=[
                    "No verified crime incident dataset supplied for the active study area.",
                    "Police incident records in this jurisdiction are not openly published as point-level spatial data.",
                    "Annual district-level police aggregates lack the spatial precision required for pedestrian routing.",
                    "SafePath Finder strictly refuses to fabricate synthetic crime records."
                ],
                records=[],
                file_path=target_path
            )

        records: List[CrimeRecord] = []
        categories_set = set()
        timestamps: List[str] = []

        try:
            with open(target_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = [h.strip().lower() for h in (reader.fieldnames or [])]

                # Privacy Check: Disallow PII columns in crime datasets
                for h in headers:
                    if any(p in h for p in PROHIBITED_PII_COLUMNS):
                        raise DataQualityError(
                            f"Crime dataset contains prohibited personal identifying column '{h}'. "
                            "Datasets containing personal names, contact info, or victim details are strictly rejected."
                        )

                # Required minimal schema
                required_cols = {"latitude", "longitude", "category"}
                if not required_cols.issubset(set(headers)):
                    # Check for alternative naming
                    alt_mapping = {"lat": "latitude", "lon": "longitude", "lng": "longitude", "offense": "category"}
                    missing = required_cols - set(headers)
                    if missing and not any(k in headers for k in alt_mapping):
                        raise DataQualityError(
                            f"Crime dataset missing required columns: {missing}. Found: {headers}"
                        )

                row_idx = 0
                for row in reader:
                    row_idx += 1
                    try:
                        # Extract coordinates
                        lat_val = float(row.get("latitude") or row.get("lat"))
                        lon_val = float(row.get("longitude") or row.get("lon") or row.get("lng"))

                        if not (-90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0):
                            logger.warning(f"Row {row_idx}: Invalid coordinates ({lat_val}, {lon_val}), skipping.")
                            continue

                        category = (row.get("category") or row.get("offense") or "unspecified").strip().lower()
                        inc_id = row.get("incident_id") or row.get("id") or f"crim-{row_idx}"
                        ts = row.get("timestamp") or row.get("date") or datetime.now(timezone.utc).isoformat()
                        spatial_prec = row.get("spatial_precision") or "block_level"
                        source = row.get("source") or os.path.basename(target_path)
                        is_fixture = (row.get("is_fixture", "").lower() in {"true", "1", "yes"})

                        records.append(
                            CrimeRecord(
                                incident_id=inc_id,
                                category=category,
                                timestamp=ts,
                                latitude=lat_val,
                                longitude=lon_val,
                                spatial_precision=spatial_prec,
                                source=source,
                                is_fixture=is_fixture
                            )
                        )
                        categories_set.add(category)
                        timestamps.append(ts)
                    except (ValueError, TypeError) as parse_err:
                        logger.warning(f"Row {row_idx}: Failed to parse numeric coordinates: {parse_err}")
                        continue

        except Exception as e:
            if isinstance(e, DataQualityError):
                raise
            raise DataQualityError(f"Failed to read crime dataset at {target_path}: {e}") from e

        timestamps.sort()
        date_range = (timestamps[0], timestamps[-1]) if timestamps else None

        return CrimeDatasetResult(
            is_loaded=True,
            record_count=len(records),
            source_name=os.path.basename(target_path),
            spatial_precision="block_level",
            licensing="User-Supplied Research Dataset",
            date_range=date_range,
            categories=sorted(list(categories_set)),
            limitations=[
                "Reporting rate varies significantly by demographic and social factors.",
                "Spatial precision may reflect police station booking locations rather than exact occurrence points.",
                "Temporal delay between incident occurrence and record filing."
            ],
            records=records,
            file_path=target_path
        )

    def get_incidents_in_study_area(
        self,
        study_area: StudyArea,
        file_path: Optional[str] = None
    ) -> List[CrimeRecord]:
        result = self.load_crime_dataset(file_path)
        if not result.is_loaded:
            return []

        return [r for r in result.records if study_area.contains_point(r.latitude, r.longitude)]
