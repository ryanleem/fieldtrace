from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    postgres_password: str | None = Field(None, exclude=True, repr=False)
    database_url: str = Field(default="", validate_default=True, repr=False)

    @field_validator('database_url')
    @classmethod
    def local_database_url(cls, value: str, info: ValidationInfo) -> str:
        # An explicit URL still wins for existing/custom database installations.
        if value:
            return value
        return URL.create('postgresql+psycopg', username='guardian',
                          password=info.data.get('postgres_password'), host='127.0.0.1',
                          port=55432, database='guardian').render_as_string(hide_password=False)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str | None = None
    embedding_batch_size: int = Field(32, ge=1)
    embedding_device: str = "cpu"
    embedding_threads: int = Field(4, ge=1)
    rrf_k: int = Field(60, ge=1)
    semantic_top_n: int = Field(20, ge=1, le=500)
    keyword_top_n: int = Field(20, ge=1, le=500)
    hybrid_top_k: int = Field(10, ge=1, le=100)
    manuals_dir: Path = ROOT / "data/manuals"
    processed_dir: Path = ROOT / "data/processed"
    model_cache: Path = ROOT / ".cache/models"
    uploads_dir: Path = ROOT / "data/uploads"
    max_inspection_images: int = Field(30, ge=1, le=100)
    max_inspection_image_bytes: int = Field(10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    max_inspection_image_pixels: int = Field(16_000_000, ge=1, le=40_000_000)
    vision_provider: str = "openai"
    vision_model: str = "gpt-4.1-mini-2025-04-14"
    openai_api_key: str | None = Field(None, exclude=True, repr=False)
    gemini_api_key: str | None = Field(None, exclude=True, repr=False)
    gemini_vision_model: str = Field('gemini-2.5-flash', pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
    vision_timeout_seconds: float = Field(60, ge=1, le=180)
    troubleshooting_model: str = 'gpt-4.1-mini-2025-04-14'
    troubleshooting_timeout_seconds: float = Field(60, ge=1, le=180)
    troubleshooting_top_k: int = Field(8, ge=2, le=12)
    troubleshooting_max_llm_calls: int = Field(48, ge=4, le=80)


@lru_cache
def get_settings():
    return Settings()
