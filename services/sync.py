"""Persist normalized scraper results and track price changes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PriceHistory, Property
from scrapers.base import BaseScraper, PropertyDTO

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncResult:
    inserted: int = 0
    updated: int = 0
    price_changes: int = 0
    skipped: int = 0
    invalid_removed: int = 0


class SyncService:
    """Portal-agnostic synchronization of DTOs into the property store."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, scraper: BaseScraper) -> SyncResult:
        return self.sync(scraper.scrape())

    def sync(self, items: list[PropertyDTO]) -> SyncResult:
        result = SyncResult()
        for dto in items:
            if not dto.portal_id or not dto.url or not dto.title:
                result.skipped += 1
                continue
            existing = self.session.scalar(
                select(Property).where(Property.portal == dto.portal, Property.portal_id == dto.portal_id)
            )
            if existing is None:
                self.session.add(Property(**self._values(dto), last_price=dto.price))
                result.inserted += 1
                continue
            if existing.price != dto.price:
                self.session.add(PriceHistory(property=existing, old_price=existing.price, new_price=dto.price))
                existing.last_price = existing.price
                result.price_changes += 1
            for key, value in self._values(dto).items():
                setattr(existing, key, value)
            existing.last_seen = datetime.now(timezone.utc)
            result.updated += 1
        self.session.flush()
        portals = {item.portal for item in items}
        if portals:
            invalid_records = self.session.scalars(
                select(Property).where(
                    Property.portal.in_(portals),
                    Property.price.is_(None),
                    Property.living_area.is_(None),
                    Property.land_area.is_(None),
                )
            )
            for invalid_record in invalid_records:
                LOGGER.warning(
                    "Removing non-listing record %s from portal %s",
                    invalid_record.url,
                    invalid_record.portal,
                )
                self.session.delete(invalid_record)
                result.invalid_removed += 1
            self.session.flush()
        LOGGER.info("Sync complete: %s", result)
        return result

    @staticmethod
    def _values(dto: PropertyDTO) -> dict[str, object]:
        price_per_m2: Decimal | None = None
        if dto.price is not None and dto.living_area:
            price_per_m2 = (dto.price / dto.living_area).quantize(Decimal("0.01"))
        return {
            "portal": dto.portal, "portal_id": dto.portal_id, "url": dto.url, "title": dto.title,
            "description": dto.description, "property_type": dto.property_type, "price": dto.price,
            "price_per_m2": price_per_m2, "living_area": dto.living_area, "land_area": dto.land_area,
            "rooms": dto.rooms, "year": dto.year, "city": dto.city, "municipality": dto.municipality,
            "county": dto.county, "latitude": dto.latitude, "longitude": dto.longitude,
            "images": json.dumps(dto.images, ensure_ascii=False), "agent": dto.agent, "phone": dto.phone,
        }
