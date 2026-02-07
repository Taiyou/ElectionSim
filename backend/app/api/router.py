from __future__ import annotations

from fastapi import APIRouter

from app.api.districts import router as districts_router
from app.api.health import router as health_router
from app.api.predictions import router as predictions_router
from app.api.prompts import router as prompts_router
from app.api.proportional import router as proportional_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(districts_router)
api_router.include_router(predictions_router)
api_router.include_router(proportional_router)
api_router.include_router(prompts_router)
