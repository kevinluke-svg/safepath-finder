from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.routes import router as routes_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.reports import router as reports_router
from app.api.v1.journeys import router as journeys_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.admin import router as admin_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.geocoding import router as geocoding_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(routes_router)
api_v1_router.include_router(geocoding_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(journeys_router)
api_v1_router.include_router(contacts_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(feedback_router)

