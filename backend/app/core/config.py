import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SafePath Finder Backend"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security & Encryption
    SECRET_KEY: str = "insecure_dev_secret_key_minimum_32_characters_long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    FIELD_ENCRYPTION_KEY: Union[str, None] = None

    # Mail / Telephony Integration
    SMTP_HOST: Union[str, None] = None
    SMTP_PORT: int = 587
    SMTP_USER: Union[str, None] = None
    SMTP_PASSWORD: Union[str, None] = None
    SMTP_FROM: str = "noreply@safepath.org"
    SMTP_TLS: bool = True
    FRONTEND_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "sqlite:///./safepath.db"

    @field_validator("DATABASE_URL", mode="before")
    def resolve_sqlite_path(cls, v):
        if isinstance(v, str) and (v == "sqlite:///./safepath.db" or v == "sqlite:///safepath.db"):
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            db_path = os.path.join(backend_dir, "safepath.db")
            return f"sqlite:///{db_path}"
        return v

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://localhost:8001,http://127.0.0.1:8001"

    # Governance & Retention
    DATA_RETENTION_DAYS: int = 365
    FRESHNESS_THRESHOLD_DAYS: int = 30
    OUTDATED_THRESHOLD_DAYS: int = 90
    AUTO_FLAG_KEYWORDS: str = "harassment, assault, dark, broken, hazard"
    REQUIRE_MODERATOR_APPROVAL: bool = True

    # Geospatial & Study Area Configuration
    STUDY_AREA_NAME: str = "Bengaluru Pilot Corridor"
    STUDY_AREA_BBOX_SOUTH: float = 12.9200
    STUDY_AREA_BBOX_WEST: float = 77.5700
    STUDY_AREA_BBOX_NORTH: float = 12.9850
    STUDY_AREA_BBOX_EAST: float = 77.6200
    STUDY_AREA_PLACE_NAME: Union[str, None] = None
    GEOSPATIAL_CACHE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache")
    CRIME_DATA_FILE: Union[str, None] = None

    # Routing Engine & Edge Cost Parameters (Provisional Research Configuration)
    WALKING_SPEED_MPS: float = 1.2  # Nominal pedestrian walking speed = 72 m/min
    ROUTING_LAMBDA_BALANCED: float = 1.0  # Moderate risk penalty weight
    ROUTING_LAMBDA_SAFETY: float = 3.0  # High risk penalty weight (lambda_safety > lambda_balanced)
    ROUTING_DEFAULT_R_UNKNOWN: float = 0.5  # Modeling prior for unavailable evidence (0.0=optimistic, 1.0=pessimistic)
    ROUTING_MODEL_VERSION: str = "2.0.0"  # Multi-criteria scoring model version
    ROUTING_DEFAULT_DEPARTURE_PERIOD: str = "evening"  # Default departure period: daytime, evening, night
    ROUTING_WEIGHT_CRIME: float = 0.25  # Relative indicator weight for crime density (v2.0)
    ROUTING_WEIGHT_LIGHTING: float = 0.25  # Relative indicator weight for lighting state (v2.0)
    ROUTING_WEIGHT_COMMUNITY: float = 0.15  # Relative indicator weight for community hazard reports (v2.0)
    ROUTING_WEIGHT_INFRASTRUCTURE: float = 0.15  # Relative indicator weight for pedestrian infrastructure (v2.0)
    ROUTING_WEIGHT_DOG: float = 0.15  # Relative indicator weight for verified street dog encounters (v2.0)
    ROUTING_WEIGHT_ASSISTANCE: float = 0.05  # Relative indicator weight for emergency facility isolation penalty (v2.0)
    ROUTING_MAX_DETOUR_RATIO: float = 1.6  # Maximum acceptable detour multiplier over fastest duration
    ROUTING_MIN_COVERAGE_THRESHOLD: float = 0.30  # Coverage Q below this flags route as insufficient evidence
    ROUTING_ALTERNATIVE_OVERLAP_THRESHOLD: float = 0.50  # Jaccard/length similarity threshold to filter near-duplicate paths
    ROUTING_MAX_ALTERNATIVES: int = 3  # Maximum distinct loopless alternatives via Yen's algorithm
    ROUTING_MAX_SNAP_DISTANCE_METERS: float = 250.0  # Maximum distance to snap coordinate to pedestrian street network
    ROUTING_NEARBY_CORRIDOR_METERS: float = 500.0  # Spatial proximity threshold (meters) for nearby facilities and landmarks
    ROUTING_DOG_CORRIDOR_METERS: float = 200.0  # Spatial proximity corridor (meters) for street dog sightings and encounters
    ROUTING_MAX_NEARBY_PLACES: int = 10  # Maximum nearby places to return per route

    # Geocoding & Location Search Configuration
    GEOCODING_PROVIDER: str = "nominatim"  # "nominatim" (default OpenStreetMap provider)
    GEOCODING_BASE_URL: str = "https://nominatim.openstreetmap.org"
    GEOCODING_USER_AGENT: str = "SafePathFinder/1.0 (contact: safepath-research@safepath.org)"
    GEOCODING_API_KEY: Union[str, None] = None  # Optional private API key if configured
    GEOCODING_TIMEOUT_SECONDS: float = 8.0
    GEOCODING_CACHE_TTL_SECONDS: int = 3600  # 1 hour in-memory cache
    GEOCODING_BOUND_TO_REGION: bool = False  # If True, restricts results to regional viewbox



    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]


settings = Settings()
