"""
SafePath Finder — Geospatial Foundation & Evidence Adapters
"""

from app.geospatial.exceptions import (
    GeospatialError,
    InvalidCoordinateError,
    OutOfCoverageError,
    InvalidStudyAreaError,
    NetworkRetrievalError,
    DisconnectedNetworkError,
    DatasetNotFoundError,
    DataQualityError,
)
from app.geospatial.study_area import StudyArea
from app.geospatial.network_adapter import (
    BaseNetworkAdapter,
    OsmNetworkAdapter,
    NetworkResult,
)
from app.geospatial.lighting_adapter import (
    BaseLightingAdapter,
    OsmLightingAdapter,
    LightingAuditResult,
)
from app.geospatial.facilities_adapter import (
    BaseFacilityAdapter,
    OsmFacilityAdapter,
    FacilityPoint,
    FacilityAuditResult,
)
from app.geospatial.crime_adapter import (
    BaseCrimeAdapter,
    CsvCrimeAdapter,
    CrimeRecord,
    CrimeDatasetResult,
)
from app.geospatial.community_adapter import (
    BaseCommunityAdapter,
    DatabaseCommunityAdapter,
    CommunityIncident,
    CommunityAuditResult,
)
from app.geospatial.spatial_matcher import (
    SpatialMatcher,
    SpatialMatchResult,
)
from app.geospatial.facility_router import (
    FacilityRouter,
    FacilityProximity,
)
from app.geospatial.lighting_processor import (
    LightingProcessor,
    EdgeLightingClassification,
)
from app.geospatial.crime_processor import (
    CrimeProcessor,
    ValidatedCrimeRecord,
    CrimeProcessingSummary,
    SEVERITY_MAPPING,
)
from app.geospatial.community_processor import (
    CommunityProcessor,
    ProcessedCommunityObservation,
    FEEDBACK_CATEGORY_MAPPING,
)
from app.geospatial.evidence_pipeline import (
    EvidencePipeline,
)

__all__ = [
    "GeospatialError",
    "InvalidCoordinateError",
    "OutOfCoverageError",
    "InvalidStudyAreaError",
    "NetworkRetrievalError",
    "DisconnectedNetworkError",
    "DatasetNotFoundError",
    "DataQualityError",
    "StudyArea",
    "BaseNetworkAdapter",
    "OsmNetworkAdapter",
    "NetworkResult",
    "BaseLightingAdapter",
    "OsmLightingAdapter",
    "LightingAuditResult",
    "BaseFacilityAdapter",
    "OsmFacilityAdapter",
    "FacilityPoint",
    "FacilityAuditResult",
    "BaseCrimeAdapter",
    "CsvCrimeAdapter",
    "CrimeRecord",
    "CrimeDatasetResult",
    "BaseCommunityAdapter",
    "DatabaseCommunityAdapter",
    "CommunityIncident",
    "CommunityAuditResult",
    "SpatialMatcher",
    "SpatialMatchResult",
    "FacilityRouter",
    "FacilityProximity",
    "LightingProcessor",
    "EdgeLightingClassification",
    "CrimeProcessor",
    "ValidatedCrimeRecord",
    "CrimeProcessingSummary",
    "SEVERITY_MAPPING",
    "CommunityProcessor",
    "ProcessedCommunityObservation",
    "FEEDBACK_CATEGORY_MAPPING",
    "EvidencePipeline",
]
