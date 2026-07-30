from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.app_secrets import MANAGED_SECRET_KEYS, delete_secret, set_secret
from app.schemas.settings import (
    SecretStatusListResponse,
    SecretStatusResponse,
    SecretUpsertRequest,
)
from app.services.secrets import all_secret_statuses, secret_status

router = APIRouter(prefix="/settings", tags=["settings"])


def _require_managed_key(key: str) -> None:
    if key not in MANAGED_SECRET_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown secret key: {key!r}",
        )


@router.get("/secrets", response_model=SecretStatusListResponse)
def list_secret_statuses(db: Session = Depends(get_db)) -> SecretStatusListResponse:
    return SecretStatusListResponse(secrets=all_secret_statuses(db))


@router.put("/secrets/{key}", response_model=SecretStatusResponse)
def save_secret(
    key: str,
    payload: SecretUpsertRequest,
    db: Session = Depends(get_db),
) -> SecretStatusResponse:
    _require_managed_key(key)
    set_secret(db, key=key, value=payload.value)
    return SecretStatusResponse(**secret_status(db, key))


@router.delete("/secrets/{key}", response_model=SecretStatusResponse)
def clear_secret(key: str, db: Session = Depends(get_db)) -> SecretStatusResponse:
    _require_managed_key(key)
    delete_secret(db, key=key)
    return SecretStatusResponse(**secret_status(db, key))
