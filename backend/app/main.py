from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.models.base import Base
from app.db.seed import seed_database
from app.api.v1 import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize schema and seed demo fixtures on startup."""
    # Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    
    # Seed initial fixtures if tables are empty
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Explainable walking navigation backend emphasizing transparent evidence quality and explicit uncertainty.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS Middleware configured strictly for allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API V1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["System Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["System Health"])
def health_check():
    """System health and operational status endpoint."""
    return {
        "status": "operational",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }


# Custom structured error handlers for clean client error rendering
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Structured validation error response matching API expectations."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"], "type": error["type"]})
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": 422,
            "message": "Input validation failed. Please check the submitted fields.",
            "errors": errors
        }
    )


# Mount workspace root as static files for single-origin local hosting
import os
from fastapi.staticfiles import StaticFiles

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.exists(os.path.join(workspace_root, "safepath_pro.html")):
    app.mount("/", StaticFiles(directory=workspace_root, html=True), name="frontend")

