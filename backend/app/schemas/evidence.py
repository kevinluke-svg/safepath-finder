from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class SegmentTimelineItem(BaseModel):
    date: str
    event: str
    source: str


class SegmentResponse(BaseModel):
    id: str
    streetName: str
    source: str
    observedAt: datetime
    coverage: str  # adequate, limited, insufficient
    freshness: str  # fresh, stale, outdated
    state: str  # available, limited, insufficient
    riskEstimate: Optional[str] = None
    limitations: List[str] = []
    attributes: Dict[str, Any] = {}
    timeline: List[Dict[str, Any]] = []
    geometry: List[List[float]] = []

    # Extended network evidence indicators
    edgeU: Optional[int] = None
    edgeV: Optional[int] = None
    edgeKey: Optional[int] = 0
    lengthMeters: Optional[float] = None
    litStatus: str = "unmapped"  # lit, unlit, conflicting, unmapped
    nearestPoliceDistanceMeters: Optional[float] = None
    nearestPoliceWalkingMinutes: Optional[float] = None
    nearestHospitalDistanceMeters: Optional[float] = None
    nearestHospitalWalkingMinutes: Optional[float] = None
    crimeCount: int = 0
    crimeRatePerKm: float = 0.0
    communityReportsCount: int = 0
    evidenceSummary: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class RouteEvidenceResponse(BaseModel):
    routeId: str
    routeName: str
    segments: List[SegmentResponse]


class EvidenceSourceResponse(BaseModel):
    id: str
    name: str
    type: str
    coverage: str
    refreshFrequency: str
    lastIngested: datetime
    recordsCount: int
    status: str
    staleWarning: bool
    notes: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceSourceListResponse(BaseModel):
    items: List[EvidenceSourceResponse]
    total: int


class EvidenceObservationResponse(BaseModel):
    """
    Sanitized evidence observation response. Strictly excludes reporter identity,
    user IDs, emails, phone numbers, or IP addresses.
    """
    id: str
    sourceId: str
    sourceType: str
    category: str
    subcategory: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geometry: Dict[str, Any] = {}
    segmentId: Optional[str] = None
    edgeU: Optional[int] = None
    edgeV: Optional[int] = None
    edgeKey: Optional[int] = 0
    matchDistanceMeters: Optional[float] = None
    matchMethod: str
    matchStatus: str
    observedAt: datetime
    ingestedAt: datetime
    sourceAttribution: str
    verificationStatus: str
    severity: Optional[str] = None
    confidence: str
    dataState: str
    provenance: str
    limitations: List[str] = []
    attributes: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class EvidenceObservationListResponse(BaseModel):
    items: List[EvidenceObservationResponse]
    total: int
    limit: int
    offset: int


class CrimeImportResponse(BaseModel):
    isLoaded: bool
    recordCount: int
    validCount: int
    skippedCount: int
    duplicateCount: int
    dateRange: Optional[List[str]] = None
    categories: List[str] = []
    limitations: List[str] = []
    sourceName: str


class PipelineProcessResponse(BaseModel):
    studyAreaName: str
    edgesProcessed: int
    observationsPersisted: int
    crimeObservationsMatched: int
    lightingObservationsRecorded: int
    facilitiesMapped: int
    communityReportsMatched: int
    executionTimeSeconds: float
    status: str


class CoverageSummaryResponse(BaseModel):
    studyAreaName: str
    totalEdges: int
    edgesWithLighting: int
    lightingCoveragePercentage: float
    litEdgesCount: int
    unlitEdgesCount: int
    conflictingLightingEdgesCount: int
    unmappedLightingEdgesCount: int
    policeStationsCount: int
    policeAccessibleEdgesCount: int
    policeAccessiblePercentage: float
    hospitalsCount: int
    hospitalAccessibleEdgesCount: int
    hospitalAccessiblePercentage: float
    crimeIncidentsMatched: int
    communityReportsMatched: int
    dataStateBreakdown: Dict[str, int]
    dataGaps: List[str]
    caveats: List[str]

