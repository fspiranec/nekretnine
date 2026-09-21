"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime settings loaded from environment variables."""

    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'nekretnine.db').as_posix()}"
    )
    secret_key: str = os.getenv("SECRET_KEY", "change-this-key-in-production")
    opereta_base_url: str = os.getenv("OPERETA_BASE_URL", "https://www.opereta.hr")
    opereta_houses_url: str = os.getenv(
        "OPERETA_HOUSES_URL", "https://www.opereta.hr/nekretnine/?vrsta=kuce"
    )
    request_timeout: int = int(os.getenv("SCRAPER_TIMEOUT", "20"))
    scraper_max_pages: int = int(os.getenv("SCRAPER_MAX_PAGES", "30"))

