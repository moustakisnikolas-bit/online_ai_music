from fastapi import FastAPI

from app.api.routes.audio import router as audio_router
from app.api.routes.audio_jobs import router as audio_jobs_router
from app.api.routes.audio_assets import router as audio_assets_router
from app.api.routes.audio_files import router as audio_files_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.presets import router as presets_router
from app.api.routes.web import router as web_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="AION core API",
)

app.include_router(health_router)
app.include_router(audio_router, prefix="/api/v1")
app.include_router(audio_jobs_router, prefix="/api/v1")
app.include_router(audio_assets_router, prefix="/api/v1")
app.include_router(audio_files_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(presets_router, prefix="/api/v1")

app.include_router(web_router)
