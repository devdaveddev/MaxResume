"""Typed application settings, loaded from environment variables (or a .env file).

Every operational limit lives here so it can be tuned per deployment without
code changes. Variable names are the upper-case field names, e.g. MAX_FILE_MB=10.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- runtime
    env: Literal["development", "test", "production"] = "development"
    app_version: str = "1.1.0"

    # --- logging
    log_level: str = "INFO"
    log_json: bool | None = None  # default: JSON in production, readable text otherwise

    # --- storage
    storage: Literal["auto", "mongodb", "memory"] = "auto"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "maxresume"

    # --- security
    # Comma-separated "name:key" pairs, e.g. "alice:s3cret,ats-bot:k3y". Empty = auth disabled (local use).
    api_keys: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Origins allowed to embed the app in an iframe (e.g. "https://huggingface.co").
    # Empty = no framing at all (X-Frame-Options: DENY).
    frame_ancestors: str = ""

    # --- NLP
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    default_phone_region: str = "US"  # used to interpret phone numbers written without a country code

    # --- ingestion limits
    max_file_mb: float = 10
    max_batch: int = 50
    max_pdf_pages: int = 15          # longer documents are truncated (with a warning)
    max_unzipped_mb: float = 60      # DOCX/ODT zip-bomb guard
    parse_timeout_s: float = 90      # per file
    parse_workers: int = Field(default=4, ge=1, le=16)
    ocr_enabled: bool = True
    ocr_max_pages: int = 6
    ocr_dpi: int = 300
    converter_timeout_s: float = 45  # antiword / LibreOffice for .doc/.rtf/.odt

    # --- single-container mode: serve the built frontend from the API process
    static_dir: Path | None = None

    # --- demo data
    enable_samples: bool = True
    samples_dir: Path = ROOT / "sample_data"

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @property
    def use_json_logs(self) -> bool:
        return self.log_json if self.log_json is not None else self.env == "production"

    @property
    def max_file_bytes(self) -> int:
        return int(self.max_file_mb * 1024 * 1024)

    @property
    def api_key_map(self) -> dict[str, str]:
        """key -> actor name."""
        out = {}
        for pair in filter(None, (p.strip() for p in self.api_keys.split(","))):
            name, _, key = pair.partition(":")
            if key:
                out[key.strip()] = name.strip()
        return out

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
