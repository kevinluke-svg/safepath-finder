from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class EvidenceSummary(BaseModel):
    coverage: str  # adequate, limited, insufficient
    coveragePercentage: int
    freshestObservationDays: int
    freshnessState: str  # fresh, stale, outdated
    riskEstimate: str
    crimeCount: Optional[int] = 0
    lightingCoveragePercentage: Optional[float] = 0.0
    feedbackCount: Optional[int] = 0
    nearestHospitalDistanceMeters: Optional[float] = None
    nearestPoliceDistanceMeters: Optional[float] = None
    dataQualitySummary: Optional[str] = None


class StreetlightEvidenceSummary(BaseModel):
    totalDistanceMeters: float
    knownLitDistanceMeters: float
    knownUnlitDistanceMeters: float
    conflictingDistanceMeters: float
    unknownDistanceMeters: float
    litPercentage: float
    unlitPercentage: float
    conflictingPercentage: float
    unknownPercentage: float
    mappedStreetlampsCount: int = 0
    sources: List[str] = Field(default_factory=lambda: ["OpenStreetMap (Way tags 'lit=*', Node tags 'highway=street_lamp')"])
    explanation: str


class NearbyPlace(BaseModel):
    id: str
    name: str
    category: str  # police, hospital, transit, park, pharmacy, landmark
    distanceMeters: float
    walkingMinutes: Optional[float] = None
    coordinates: List[float]  # [lat, lon]
    source: str = "OpenStreetMap"
    attribution: str = "© OpenStreetMap contributors, ODbL 1.0"
    limitations: Optional[str] = None


class RouteAlternative(BaseModel):
    id: str
    name: str
    category: str  # fastest, balanced, safety_prioritized, alternative
    distanceMeters: int
    durationSeconds: int
    characteristics: List[str]
    evidenceSummary: EvidenceSummary
    explanation: str
    tradeoffs: str
    geometry: List[List[float]]
    segments: Optional[List[Dict[str, Any]]] = None
    preference: Optional[str] = None
    routeRisk: Optional[float] = None
    generalizedCost: Optional[float] = None
    evidenceCoverage: Optional[float] = None
    hasInsufficientEvidence: Optional[bool] = False
    isIdenticalToFastest: Optional[bool] = False
    identicalNotes: Optional[str] = None
    rankingFactors: Optional[List[str]] = Field(default_factory=list)
    limitations: Optional[List[str]] = Field(default_factory=list)
    sourceMetadata: Optional[Dict[str, Any]] = None
    streetlightSummary: Optional[StreetlightEvidenceSummary] = None
    nearbyPlaces: Optional[List[NearbyPlace]] = Field(default_factory=list)


class RouteCompareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    origin: str = Field(..., min_length=2, max_length=255)
    destination: str = Field(..., min_length=2, max_length=255)
    walkingMode: str = "pedestrian"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    originCoordinates: Optional[List[float]] = Field(None, description="[latitude, longitude]")
    destinationCoordinates: Optional[List[float]] = Field(None, description="[latitude, longitude]")

    @model_validator(mode="before")
    @classmethod
    def normalize_coords_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "origin_coordinates" in data and "originCoordinates" not in data:
                data["originCoordinates"] = data["origin_coordinates"]
            if "destination_coordinates" in data and "destinationCoordinates" not in data:
                data["destinationCoordinates"] = data["destination_coordinates"]
        return data


class RouteCompareResponse(BaseModel):
    origin: str
    destination: str
    walkingMode: str
    timestamp: datetime
    rankingReason: str
    routes: List[RouteAlternative]
    studyArea: Optional[Dict[str, Any]] = None

