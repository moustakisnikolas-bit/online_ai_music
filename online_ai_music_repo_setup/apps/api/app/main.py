from fastapi import FastAPI

from app.api.routes.audio import router as audio_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AION core API",
)

app.include_router(health_router)
app.include_router(audio_router, prefix="/api/v1")
