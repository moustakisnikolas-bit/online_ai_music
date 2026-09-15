from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.models import (  # noqa: F401
    AlbumBatch,
    AlbumTrack,
    AlbumTrackShort,
    AppSecret,
    AudioAsset,
    AudioJob,
    ConceptResearch,
    GenerationCost,
    InternetArchivePublication,
    OAuthState,
    Project,
    TrackRating,
    YouTubeCredential,
    YouTubePublication,
    YouTubeQuotaUsage,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Always resolve the real DB URL from the app's own settings (reads .env /
# real env vars, same source of truth app/db/session.py uses) rather than
# trusting alembic.ini's static value -- that value drifted from the real
# dev Postgres port (5435, docker-compose maps 5432 internally) at some
# point, which made `alembic current`/`upgrade head` hang trying to
# connect to a nonexistent service on 5432 instead of erroring clearly.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
