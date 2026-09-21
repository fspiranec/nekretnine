"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _default_database_url() -> str:
    """Use Vercel's writable temporary directory in serverless deployments."""
    database_path = (
        Path("/tmp/nekretnine.db")
        if os.getenv("VERCEL")
        else BASE_DIR / "data" / "nekretnine.db"
    )
    return f"sqlite:///{database_path.as_posix()}"


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime settings loaded from environment variables."""

    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", _default_database_url()))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "change-this-key-in-production"))
    opereta_base_url: str = field(default_factory=lambda: os.getenv("OPERETA_BASE_URL", "https://www.opereta.hr"))
    opereta_houses_url: str = field(
        default_factory=lambda: os.getenv(
            "OPERETA_HOUSES_URL", "https://www.opereta.hr/hr/nekretnine?vrsta=kuce"
        )
    )
    request_timeout: int = field(default_factory=lambda: int(os.getenv("SCRAPER_TIMEOUT", "20")))
    scraper_max_pages: int = field(default_factory=lambda: int(os.getenv("SCRAPER_MAX_PAGES", "30")))
    is_serverless: bool = field(default_factory=lambda: bool(os.getenv("VERCEL")))
