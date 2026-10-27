from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GeocodingResult(BaseModel):
    id: str = Field(..., description="Unique provider ID or place identifier")
    name: str = Field(..., description="Place name or landmark title")
    displayName: str = Field(..., description="Formatted full address string with locality, city, region")
    latitude: float = Field(..., description="WGS-84 latitude coordinate [-90..90]")
    longitude: float = Field(..., description="WGS-84 longitude coordinate [-180..180]")
    type: str = Field("place", description="Location type (e.g. suburb, residential, commercial, amenity, coordinate)")
    address: Dict[str, Optional[str]] = Field(default_factory=dict, description="Structured address components")
    inStudyArea: bool = Field(False, description="True if coordinates reside inside active pedestrian routing network")
    studyAreaDistanceMeters: Optional[float] = Field(None, description="Distance in meters to study area bounding box if outside")
    importance: Optional[float] = Field(None, description="Relevance or ranking score from geocoding provider")
    boundingBox: Optional[List[float]] = Field(None, description="[south, north, west, east] bounding box if provided")


class GeocodingSearchResponse(BaseModel):
    query: str
    provider: str
    count: int
    results: List[GeocodingResult]
    studyArea: Dict[str, Any]
