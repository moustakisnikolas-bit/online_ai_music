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

    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/publishing/youtube/callback"

    replicate_api_token: str = ""
    stable_audio_model: str = "stackadoc/stable-audio-open-1.0"

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
