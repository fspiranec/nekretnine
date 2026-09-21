"""Build local SQL filters and API representations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models import Property


@dataclass(slots=True)
class PropertyFilters:
    property_type: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    living_min: Decimal | None = None
    living_max: Decimal | None = None
    land_min: Decimal | None = None
    land_max: Decimal | None = None
    counties: list[str] = field(default_factory=list)
    municipalities: list[str] = field(default_factory=list)

    @classmethod
    def from_query(cls, args: Mapping[str, str], getlist: object) -> "PropertyFilters":
        list_getter = getlist  # Flask's MultiDict.getlist, kept framework-free for testing.
        return cls(
            property_type=args.get("property_type") or None,
            price_min=_decimal(args.get("price_min")), price_max=_decimal(args.get("price_max")),
            living_min=_decimal(args.get("living_min")), living_max=_decimal(args.get("living_max")),
            land_min=_decimal(args.get("land_min")), land_max=_decimal(args.get("land_max")),
            counties=list_getter("county"), municipalities=list_getter("municipality"),  # type: ignore[operator]
        )


def filtered_properties(session: Session, filters: PropertyFilters) -> list[Property]:
    query: Select[tuple[Property]] = select(Property).order_by(Property.updated_at.desc())
    pairs = ((Property.price, filters.price_min, filters.price_max),
             (Property.living_area, filters.living_min, filters.living_max),
             (Property.land_area, filters.land_min, filters.land_max))
    if filters.property_type:
        query = query.where(Property.property_type == filters.property_type)
    for column, minimum, maximum in pairs:
        if minimum is not None:
            query = query.where(column >= minimum)
        if maximum is not None:
            query = query.where(column <= maximum)
    if filters.counties:
        query = query.where(Property.county.in_(filters.counties))
    if filters.municipalities:
        query = query.where(Property.municipality.in_(filters.municipalities))
    return list(session.scalars(query.limit(2000)))


def serialize_property(item: Property) -> dict[str, object]:
    try:
        images = json.loads(item.images or "[]")
    except json.JSONDecodeError:
        images = []
    return {
        "id": item.id, "portal": item.portal, "url": item.url, "title": item.title,
        "property_type": item.property_type, "price": float(item.price) if item.price is not None else None,
        "living_area": float(item.living_area) if item.living_area is not None else None,
        "land_area": float(item.land_area) if item.land_area is not None else None,
        "city": item.city, "municipality": item.municipality, "county": item.county,
        "latitude": item.latitude, "longitude": item.longitude, "images": images,
    }


def _decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None
