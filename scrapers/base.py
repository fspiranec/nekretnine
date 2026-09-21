"""Portal-independent scraper contract and data transfer object."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True)
class PropertyDTO:
    """Normalized listing returned by every portal adapter."""

    portal: str
    portal_id: str
    url: str
    title: str
    property_type: str
    price: Decimal | None = None
    living_area: Decimal | None = None
    land_area: Decimal | None = None
    city: str | None = None
    municipality: str | None = None
    county: str | None = None
    description: str | None = None
    images: list[str] = field(default_factory=list)
    rooms: Decimal | None = None
    year: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    agent: str | None = None
    phone: str | None = None


class BaseScraper(ABC):
    """Interface implemented by each property portal."""

    @abstractmethod
    def scrape(self) -> list[PropertyDTO]:
        """Fetch current listings and normalize them."""
