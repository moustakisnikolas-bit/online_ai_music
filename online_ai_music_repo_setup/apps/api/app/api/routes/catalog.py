import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.generation_costs import OPENROUTER_METADATA, record_reported_cost
from app.schemas.catalog import (
    MetadataGenerateRequest,
    MetadataPackageResponse,
)
from app.services.llm_metadata_generator import generate_llm_metadata_package
from app.services.metadata_generator import generate_metadata_package

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post(
    "/metadata/generate",
    response_model=MetadataPackageResponse,
)
def generate_metadata(
    payload: MetadataGenerateRequest,
    db: Session = Depends(get_db),
) -> MetadataPackageResponse:
    if payload.use_llm_metadata:
        try:
            package, cost_usd = generate_llm_metadata_package(
                source_title=payload.source_title,
                mode=payload.mode,
                duration_seconds=payload.duration_seconds,
                db=db,
                context=payload.context,
                language=payload.language,
                frequency_hz=payload.frequency_hz,
                texture_mode=payload.texture_mode,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except (RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM metadata generation failed: {exc}",
            ) from exc

        record_reported_cost(
            db, kind=OPENROUTER_METADATA, reported_usd=cost_usd, reference=payload.source_title
        )
    else:
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
