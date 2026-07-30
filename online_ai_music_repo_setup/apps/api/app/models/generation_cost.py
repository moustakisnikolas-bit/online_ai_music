import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GenerationCost(Base):
    """A logged estimate of what one paid external API call cost.

    Nothing in this app currently has real-time billing visibility into
    Replicate/OpenRouter usage -- this is a running ledger built from
    per-call cost figures (either a documented estimate for the model, or
    the exact cost a provider's own response reports, when it reports one)
    so there's *some* visibility into spend per generation, which
    previously didn't exist at all.
    """

    __tablename__ = "generation_costs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    # False when a provider's response reported the exact billed cost
    # (currently: OpenRouter's images endpoint); True when it's a
    # documented per-call estimate (currently: Replicate calls, which
    # don't return billing data inline).
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
