from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AION API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://aion:aion@postgres:5432/aion"
    redis_url: str = "redis://redis:6379/0"
    generated_audio_dir: str = "data/generated/audio"
    soundfont_path: str = "data/soundfonts/GeneralUser-GS.sf2"

    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/publishing/youtube/callback"

    # YouTube Data API v3 quota bookkeeping (see repositories/youtube_quota.py).
    # The API doesn't expose real-time remaining quota, so the app keeps
    # its own ledger against these documented costs. Verified against
    # Google's real, current default (10,000 units/day, video upload
    # 1,600 units) as of 2026-07 -- a real quota increase from Google is
    # just a bigger youtube_daily_quota_budget number, no code change.
    youtube_daily_quota_budget: int = 10000
    youtube_upload_quota_cost_units: int = 1600
    youtube_playlist_write_cost_units: int = 50
    # Reserves headroom for thumbnail-set calls, incidental read calls,
    # and any manual single-video uploads the operator does concurrently
    # via the existing publishing flow, since that shares the same
    # Google Cloud project quota as the album pipeline.
    youtube_quota_safety_margin_units: int = 800

    # YouTube Shorts generation (see app/services/shorts_pipeline.py).
    # Default OFF -- flipping this on adds real production content, real
    # extra Replicate artwork spend (one vertical image per track), and
    # competes for the same shared YouTube Data API v3 daily quota pool as
    # long-form uploads (~4 total videos.insert calls/day today), so it's a
    # deliberate opt-in rather than something that starts the moment this
    # ships.
    shorts_enabled: bool = False
    # Each short costs a full videos.insert (1600 units) same as long-form,
    # so N shorts/track roughly divides real combined daily upload
    # throughput by (N+1) -- accepted tradeoff, not a bug.
    shorts_per_track: int = 5
    # 15-30s is YouTube Shorts' top-performing retention bracket for a
    # no-narrative ambient loop (nothing to "build to" -- completion rate
    # is the dominant ranking signal). 28s keeps real margin under the
    # 3-minute auto-Shorts-classification ceiling once container/encode
    # overhead is accounted for. Verified against Google's own Shorts
    # classification support page as of 2026-09 (vertical/square aspect +
    # <=3min = auto-Short, no special API field needed).
    shorts_duration_seconds: int = 28
    shorts_width: int = 1080
    shorts_height: int = 1920
    # Matches how long-form already uploads -- public immediately, no
    # manual review step.
    shorts_privacy_status: str = "public"
    # ISO date string ("YYYY-MM-DD") or None. None means every track
    # already sitting at "uploaded"/"playlist_added" -- the whole existing
    # catalog -- becomes shorts-eligible the moment shorts_enabled is
    # flipped on, same as any track reaching that status in the future.
    # Set a date here to restrict backfill to tracks uploaded on/after it.
    shorts_backfill_cutoff_date: str | None = None

    # Encrypts YouTubeCredential.access_token/refresh_token at rest -- a
    # refresh_token is a long-lived credential to the connected channel, so
    # storing it in plaintext is a real risk if the database is ever
    # exposed. Generate one with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    replicate_api_token: str = ""
    stable_audio_model: str = "stackadoc/stable-audio-open-1.0"
    # FLUX.1 [schnell] (Apache 2.0, free/open-weights model from Black
    # Forest Labs) via Replicate's hosting, not flux-1.1-pro -- chosen
    # after checking the user's own hardware (AMD integrated graphics, no
    # CUDA) ruled out running it locally at a usable speed, and no
    # genuinely free/unlimited hosted option for a good open image model
    # currently exists (Pollinations moved to paid credits; HF's free
    # tier is a limited proxy over paid providers). This keeps cost near
    # the floor (~$0.003/image, not the pro model's much higher rate)
    # while still running a real open-source model, not a closed one.
    flux_model: str = "black-forest-labs/flux-schnell"

    # Freesound (freesound.org) -- CC0-licensed real recordings for the
    # sample library. API-key auth only (no OAuth2), which is enough for
    # search and preview download; see freesound_importer.py.
    freesound_api_key: str = ""

    # Internet Archive (archive.org) -- the "free choice" publishing
    # platform (SoundCloud stopped issuing new API keys; Audius's officially
    # supported upload path is JS/TS-SDK-only, not reachable from this
    # Python backend without an unsupported, undocumented endpoint -- see
    # internet_archive_publisher.py). A static S3-like access/secret key
    # pair, self-serve from archive.org/account/s3.php -- no OAuth needed.
    internet_archive_access_key: str = ""
    internet_archive_secret_key: str = ""

    # Per-call cost estimates for spend tracking (see generation_costs.py).
    # Replicate's prediction API doesn't return exact billed cost inline,
    # so these are documented estimates, verified against the providers'
    # own pricing pages as of 2026-07 -- not guaranteed to stay current,
    # override here if actual billing drifts from these.
    stable_audio_open_cost_usd: float = 0.14
    flux_replicate_cost_usd: float = 0.003

    # Hibernating: no key configured by default. Kept ready so switching the
    # active artwork provider from Replicate to OpenRouter later needs only
    # an env var, not new code. See ai_artwork_generator.py.
    openrouter_api_key: str = ""
    openrouter_image_model: str = "bytedance-seed/seedream-4.5"
    # Best-guess default text model slug, not yet verified against a real
    # key -- same caveat as flux_model/openrouter_image_model. Check
    # openrouter.ai/models before first real use in case it's been renamed.
    openrouter_text_model: str = "anthropic/claude-3.5-haiku"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def audio_output_path(self) -> Path:
        return Path(self.generated_audio_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
