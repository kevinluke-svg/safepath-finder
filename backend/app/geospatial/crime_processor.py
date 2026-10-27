"""
SafePath Finder — Responsible Crime Evidence Processor
Validates crime datasets, rejects PII, detects duplicates, normalizes historical indicators,
and maps observations to the pedestrian street network without fabricating crime rates.
"""

import os
import csv
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict

from app.geospatial.study_area import StudyArea
from app.geospatial.spatial_matcher import SpatialMatcher, SpatialMatchResult
from app.geospatial.crime_adapter import CrimeRecord, PROHIBITED_PII_COLUMNS
from app.geospatial.exceptions import DataQualityError

logger = logging.getLogger(__name__)

# Documented Severity Taxonomy
SEVERITY_MAPPING = {
    # High Severity (Violent or direct physical danger)
    "violent_crime": "high",
    "assault": "high",
    "aggravated_assault": "high",
    "robbery": "high",
    "sexual_assault": "high",
    "homicide": "high",
    "battery": "high",
    "weapon": "high",
    "felony": "high",

    # Medium Severity (Property theft, personal intrusion, harassment)
    "theft": "medium",
    "burglary": "medium",
    "larceny": "medium",
    "harassment": "medium",
    "stalking": "medium",
    "pickpocketing": "medium",
    "vehicle_theft": "medium",
    "misdemeanor": "medium",

    # Low Severity (Civic disorder, environmental nuisance)
    "vandalism": "low",
    "public_intoxication": "low",
    "trespassing": "low",
    "disorderly_conduct": "low",
    "loitering": "low",
    "minor_infraction": "low"
}


@dataclass
class ValidatedCrimeRecord:
    """Validated crime incident with spatial precision and normalized severity."""
    incident_id: str
    category: str
    timestamp: datetime
    latitude: float
    longitude: float
    severity: Optional[str]
    spatial_precision: str
    source_name: str
    match_result: Optional[SpatialMatchResult] = None
    is_fixture: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class CrimeProcessingSummary:
    """Summary of crime dataset ingestion and spatial association."""
    source_name: str
    total_rows_read: int
    valid_records_count: int
    skipped_rows_count: int
    duplicates_detected_count: int
    matched_to_network_count: int
    unmatched_count: int
    date_range: Optional[Tuple[str, str]]
    categories_present: List[str]
    historical_window_days: int
    limitations: List[str]
    disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceName": self.source_name,
            "totalRowsRead": self.total_rows_read,
            "validRecordsCount": self.valid_records_count,
            "skippedRowsCount": self.skipped_rows_count,
            "duplicatesDetectedCount": self.duplicates_detected_count,
            "matchedToNetworkCount": self.matched_to_network_count,
            "unmatchedCount": self.unmatched_count,
            "dateRange": self.date_range,
            "categoriesPresent": self.categories_present,
            "historicalWindowDays": self.historical_window_days,
            "limitations": self.limitations,
            "disclaimer": self.disclaimer
        }


class CrimeProcessor:
    """
    Ingests and normalizes historical crime records onto pedestrian network segments.
    Refuses to present raw incident counts as personal victimization probabilities.
    Calculates historical evidence density per kilometer over defined temporal windows.
    """

    def __init__(
        self,
        historical_window_days: int = 365,
        spatial_tolerance_meters: float = 30.0
    ):
        self.historical_window_days = historical_window_days
        self.spatial_tolerance_meters = spatial_tolerance_meters

    @staticmethod
    def parse_timestamp(ts_str: str) -> Optional[datetime]:
        """Parses common timestamp formats into UTC datetime."""
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d"
        ]
        clean_str = ts_str.strip()
        for fmt in formats:
            try:
                dt = datetime.strptime(clean_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(clean_str)
        except Exception:
            return None

    def ingest_csv(
        self,
        file_path: str,
        study_area: Optional[StudyArea] = None
    ) -> Tuple[List[ValidatedCrimeRecord], CrimeProcessingSummary]:
        """
        Parses and validates a CSV file of historical crime incidents.
        Strictly rejects PII headers and detects duplicates.
        """
        if not os.path.isfile(file_path):
            raise DataQualityError(f"Crime dataset file does not exist: {file_path}")

        records: List[ValidatedCrimeRecord] = []
        seen_incident_ids: Set[str] = set()
        seen_fingerprints: Set[str] = set()

        total_rows = 0
        skipped_rows = 0
        duplicates = 0
        categories_found: Set[str] = set()
        valid_timestamps: List[datetime] = []

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]

            # Privacy Guarantee: Reject any file containing sensitive personal info
            for h in headers:
                if any(p in h for p in PROHIBITED_PII_COLUMNS):
                    raise DataQualityError(
                        f"Prohibited personal identifying column '{h}' detected in crime dataset. "
                        "SafePath Finder strictly rejects files containing personal identities or contact info."
                    )

            # Minimal columns
            has_lat = any(c in headers for c in ["latitude", "lat"])
            has_lon = any(c in headers for c in ["longitude", "lon", "lng"])
            has_cat = any(c in headers for c in ["category", "offense", "type"])
            if not (has_lat and has_lon and has_cat):
                raise DataQualityError(
                    f"Crime dataset missing required columns (latitude, longitude, category). Found: {headers}"
                )

            for row in reader:
                total_rows += 1
                try:
                    lat_str = row.get("latitude") or row.get("lat")
                    lon_str = row.get("longitude") or row.get("lon") or row.get("lng")
                    if not lat_str or not lon_str:
                        skipped_rows += 1
                        continue

                    lat_val = float(lat_str)
                    lon_val = float(lon_str)

                    # Validate geographic boundary
                    if not (-90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0):
                        skipped_rows += 1
                        continue

                    if study_area and not study_area.contains_point(lat_val, lon_val):
                        # Point is outside configured study area
                        skipped_rows += 1
                        continue

                    category = (row.get("category") or row.get("offense") or "unspecified").strip().lower()
                    inc_id = (row.get("incident_id") or row.get("id") or f"crim-{total_rows}").strip()
                    ts_str = row.get("timestamp") or row.get("date") or datetime.now(timezone.utc).isoformat()
                    parsed_ts = self.parse_timestamp(ts_str) or datetime.now(timezone.utc)

                    # Duplicate check
                    fingerprint = f"{round(lat_val, 4)}_{round(lon_val, 4)}_{parsed_ts.date()}_{category}"
                    if inc_id in seen_incident_ids or fingerprint in seen_fingerprints:
                        duplicates += 1
                        continue

                    seen_incident_ids.add(inc_id)
                    seen_fingerprints.add(fingerprint)

                    # Severity mapping
                    raw_severity = row.get("severity")
                    if raw_severity and raw_severity.strip().lower() in {"low", "medium", "high"}:
                        severity = raw_severity.strip().lower()
                    else:
                        severity = SEVERITY_MAPPING.get(category, None)

                    prec = row.get("spatial_precision") or "block_level"
                    src = row.get("source") or os.path.basename(file_path)
                    is_fix = row.get("is_fixture", "").lower() in {"true", "1", "yes"}

                    rec = ValidatedCrimeRecord(
                        incident_id=inc_id,
                        category=category,
                        timestamp=parsed_ts,
                        latitude=lat_val,
                        longitude=lon_val,
                        severity=severity,
                        spatial_precision=prec,
                        source_name=src,
                        is_fixture=is_fix
                    )
                    records.append(rec)
                    categories_found.add(category)
                    valid_timestamps.append(parsed_ts)

                except (ValueError, TypeError) as parse_err:
                    skipped_rows += 1
                    continue

        valid_timestamps.sort()
        date_range = (
            valid_timestamps[0].date().isoformat(),
            valid_timestamps[-1].date().isoformat()
        ) if valid_timestamps else None

        summary = CrimeProcessingSummary(
            source_name=os.path.basename(file_path),
            total_rows_read=total_rows,
            valid_records_count=len(records),
            skipped_rows_count=skipped_rows,
            duplicates_detected_count=duplicates,
            matched_to_network_count=0,
            unmatched_count=len(records),
            date_range=date_range,
            categories_present=sorted(list(categories_found)),
            historical_window_days=self.historical_window_days,
            limitations=[
                "Incident density reflects police reporting practices, jurisdictional boundaries, and pedestrian exposure.",
                "Reporting likelihood varies substantially by demographic and socioeconomic factors.",
                "Historical evidence indicators must never be interpreted as individual victimization probabilities."
            ],
            disclaimer=(
                "Crime records provide retrospective environmental indicators. SafePath Finder explicitly rejects "
                "probabilistic risk modeling based on raw historical counts."
            )
        )

        return records, summary

    def match_records_to_network(
        self,
        records: List[ValidatedCrimeRecord],
        matcher: SpatialMatcher
    ) -> Tuple[List[ValidatedCrimeRecord], Dict[Tuple[int, int, int], List[ValidatedCrimeRecord]]]:
        """
        Associates validated crime records with pedestrian network edges using SpatialMatcher.
        Filters records by the configured temporal window.
        """
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=self.historical_window_days)

        matched_records: List[ValidatedCrimeRecord] = []
        edge_map: Dict[Tuple[int, int, int], List[ValidatedCrimeRecord]] = {}

        for rec in records:
            # Check temporal window (retain recent incidents for evidence indicator)
            if rec.timestamp < cutoff_date:
                continue

            match_res = matcher.match_point(
                rec.latitude,
                rec.longitude,
                tolerance_meters=self.spatial_tolerance_meters
            )
            rec.match_result = match_res
            matched_records.append(rec)

            if match_res.status == "matched" and match_res.edge_u is not None:
                edge_key = (match_res.edge_u, match_res.edge_v, match_res.edge_key or 0)
                if edge_key not in edge_map:
                    edge_map[edge_key] = []
                edge_map[edge_key].append(rec)

        return matched_records, edge_map

    @staticmethod
    def calculate_segment_crime_indicator(
        matched_incidents: List[ValidatedCrimeRecord],
        segment_length_meters: float
    ) -> Tuple[int, float, Dict[str, Any]]:
        """
        Normalizes crime incident count by segment length to provide a length-adjusted
        historical evidence indicator (incidents per kilometer).
        """
        count = len(matched_incidents)
        length_km = max(segment_length_meters / 1000.0, 0.05)  # Floor at 50m to prevent divide-by-zero
        rate_per_km = round(count / length_km, 2)

        severity_counts = {"high": 0, "medium": 0, "low": 0, "unclassified": 0}
        for inc in matched_incidents:
            if inc.severity in severity_counts:
                severity_counts[inc.severity] += 1
            else:
                severity_counts["unclassified"] += 1

        summary = {
            "indicatorType": "historical_crime_density",
            "count": count,
            "ratePerKm": rate_per_km,
            "severityBreakdown": severity_counts,
            "label": "Historical Crime Evidence Indicator (Incidents per km)",
            "caveat": (
                "Historical count normalized by segment length. Does not represent individual victimization risk "
                "or current time-of-day hazard."
            )
        }
        return count, rate_per_km, summary
