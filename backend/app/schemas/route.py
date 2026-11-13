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
    category: str  # police, hospital, pharmacy, transit, education, civic_building, park, landmark, commercial_hub
    distanceMeters: float
    walkingMinutes: Optional[float] = None
    coordinates: List[float]  # [lat, lon]
    isAssistance: bool = False
    distanceType: str = "straight_line"  # "straight_line" or "pedestrian_network"
    source: str = "OpenStreetMap"
    attribution: str = "© OpenStreetMap contributors, ODbL 1.0"
    limitations: Optional[str] = None


class DogEncounterSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    totalReportsCount: int = 0
    eligibleReportsCount: int = 0
    approvedReportsCount: int = 0
    sightingCount: int = 0
    groupCount: int = 0
    aggressiveCount: int = 0
    biteCount: int = 0
    freshestReportDays: Optional[int] = None
    affectedRouteLengthMeters: float = 0.0
    affectedLengthPercentage: float = 0.0
    corridorMeters: float = 200.0
    totalRouteLengthMeters: Optional[float] = 0.0
    usableDogEvidenceLengthMeters: Optional[float] = 0.0
    explanation: str
    guidance: List[str] = Field(default_factory=list)


class PedestrianInfrastructureSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    totalDistanceMeters: float
    sidewalkDocumentedLengthMeters: float
    sidewalkDocumentedPercentage: float
    sidewalkUnmappedLengthMeters: float
    sidewalkUnmappedPercentage: float
    sidewalkAbsentLengthMeters: float
    sidewalkAbsentPercentage: float
    crossingCount: int = 0
    signalizedCrossingCount: int = 0
    tactilePavingCount: int = 0
    highDifficultyCrossingsCount: int = 0
    constructionHazardsCount: int = 0
    wheelchairAccessibleCount: int = 0
    explanation: str
    guidance: List[str] = Field(default_factory=list)
    dataLimitation: str = "Sidewalk presence on OpenStreetMap is incomplete in developing urban corridors; missing data is preserved as unmapped."

    # Backwards compatibility and convenient access aliases
    sidewalkCoveragePercentage: Optional[float] = None
    knownSidewalkDistanceMeters: Optional[float] = None
    unmappedSidewalkDistanceMeters: Optional[float] = None
    absentSidewalkDistanceMeters: Optional[float] = None
    highDifficultyCrossings: Optional[int] = None


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
    dogEncounterSummary: Optional[DogEncounterSummary] = None
    pedestrianInfrastructureSummary: Optional[PedestrianInfrastructureSummary] = None
    # Phase 2 Multi-Dimensional and Temporal Extensions
    departurePeriod: Optional[str] = "daytime"
    stepFree: Optional[bool] = False
    adverseRiskScore: Optional[float] = None
    overlapWithFastest: Optional[float] = None
    explanationDetails: Optional[Dict[str, Any]] = None
    walkingSpeedMps: Optional[float] = 1.2
    walkingSpeedKmh: Optional[float] = 4.3


class RouteCompareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    origin: str = Field(..., min_length=2, max_length=255)
    destination: str = Field(..., min_length=2, max_length=255)
    walkingMode: str = "pedestrian"
    departurePeriod: Optional[str] = "daytime"  # "daytime", "evening", "night"
    stepFree: Optional[bool] = False
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
            if "departure_period" in data and "departurePeriod" not in data:
                data["departurePeriod"] = data["departure_period"]
            elif "time_of_day" in data and "departurePeriod" not in data:
                data["departurePeriod"] = data["time_of_day"]
            elif "timeOfDay" in data and "departurePeriod" not in data:
                data["departurePeriod"] = data["timeOfDay"]
            elif "departurePeriod" not in data and "preferences" in data and isinstance(data["preferences"], dict):
                pref_dp = data["preferences"].get("departurePeriod") or data["preferences"].get("departure_period")
                if pref_dp:
                    data["departurePeriod"] = pref_dp
            if "step_free" in data and "stepFree" not in data:
                data["stepFree"] = data["step_free"]
        return data


class RouteCompareResponse(BaseModel):
    origin: str
    destination: str
    walkingMode: str
    timestamp: datetime
    rankingReason: str
    routes: List[RouteAlternative]
    studyArea: Optional[Dict[str, Any]] = None

