import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSecret(Base):
    """A user-saved API key/credential, encrypted at rest.

    One row per managed key (see repositories/app_secrets.py's
    MANAGED_SECRET_KEYS), saved through the Settings page instead of
    .env. value_encrypted is produced by services/token_encryption.py's
    encrypt_token -- reusing the same mechanism already used for
    YouTubeCredential's OAuth tokens, not a second encryption scheme.
    """

    __tablename__ = "app_secrets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
