from functools import lru_cache
from pathlib import Path
from typing import Literal

from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: Literal['development', 'production'] = 'development'
    supabase_url: str = ''
    supabase_jwt_audience: str = 'authenticated'
    demo_requests_per_minute: int = Field(120, ge=1, le=1000)
    demo_writes_per_hour: int = Field(60, ge=1, le=1000)
    demo_provider_actions_per_hour: int = Field(8, ge=1, le=100)
    demo_upload_quota_bytes: int = Field(256 * 1024 * 1024, ge=1024)
    postgres_password: str | None = Field(None, exclude=True, repr=False)
    database_url: str = Field(default="", validate_default=True, repr=False)

    @field_validator('database_url')
    @classmethod
    def local_database_url(cls, value: str, info: ValidationInfo) -> str:
        # An explicit URL still wins for existing/custom database installations.
        if value:
            # Select the installed psycopg3 driver; preserve credentials/query/SSL bytes.
            for prefix in ('postgresql://', 'postgres://'):
                if value.startswith(prefix):
                    return 'postgresql+psycopg://' + value[len(prefix):]
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
    document_ocr_enabled: bool = False
    manuals_dir: Path = ROOT / "data/manuals"
    processed_dir: Path = ROOT / "data/processed"
    model_cache: Path = ROOT / ".cache/models"
    uploads_dir: Path = Field(ROOT / "data/uploads",
                              validation_alias=AliasChoices('UPLOAD_ROOT', 'UPLOADS_DIR', 'uploads_dir'))
    cors_allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'

    @field_validator('cors_allowed_origins')
    @classmethod
    def validate_origins(cls, value: str) -> str:
        origins = list(dict.fromkeys(part.strip() for part in value.split(',') if part.strip()))
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path or parsed.query
                    or parsed.fragment or '*' in origin):
                raise ValueError('CORS origins must be explicit HTTP(S) origins without paths or wildcards')
            try:
                parsed.port
            except ValueError as exc:
                raise ValueError('Invalid CORS origin port') from exc
        return ','.join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return self.cors_allowed_origins.split(',') if self.cors_allowed_origins else []

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
