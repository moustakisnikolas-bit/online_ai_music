from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OAuthState(Base):
    """
    A single-use CSRF token issued for an OAuth authorize/callback round
    trip. The callback handler must find and delete a matching, unexpired
    row before trusting the redirect -- without this, anything that can
    trigger a callback request (e.g. a malicious page the user visits while
    logged in) could bind an attacker's OAuth code to this app's session.
    """

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
