from fastapi import APIRouter

from app.schemas.catalog import (
    MetadataGenerateRequest,
    MetadataPackageResponse,
)
from app.services.metadata_generator import generate_metadata_package

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post(
    "/metadata/generate",
    response_model=MetadataPackageResponse,
)
def generate_metadata(
    payload: MetadataGenerateRequest,
) -> MetadataPackageResponse:
    package = generate_metadata_package(
        source_title=payload.source_title,
        mode=payload.mode,
        duration_seconds=payload.duration_seconds,
        context=payload.context,
        language=payload.language,
        frequency_hz=payload.frequency_hz,
        texture_mode=payload.texture_mode,
    )

    return MetadataPackageResponse(
        title=package.title,
        subtitle=package.subtitle,
        description=package.description,
        keywords=package.keywords,
        category=package.category,
        language=package.language,
        compliance_note=package.compliance_note,
    )
