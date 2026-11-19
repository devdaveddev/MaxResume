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

    env: Literal["development", "test", "production"] = "development"
    app_version: str = "1.1.0"

    log_level: str = "INFO"
    log_json: bool | None = None

    storage: Literal["auto", "mongodb", "memory"] = "auto"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "maxresume"

    api_keys: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frame_ancestors: str = ""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    default_phone_region: str = "US"

    max_file_mb: float = 10
    max_batch: int = 50
    max_pdf_pages: int = 15
    max_unzipped_mb: float = 60
    parse_timeout_s: float = 90
    parse_workers: int = Field(default=4, ge=1, le=16)
    ocr_enabled: bool = True
    ocr_max_pages: int = 6
    ocr_dpi: int = 300
    converter_timeout_s: float = 45

    static_dir: Path | None = None

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
