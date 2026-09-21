"""Persistence models for normalized real-estate data."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Property(Base):
    """A portal-independent current snapshot of a property listing."""

    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("portal", "portal_id", name="uq_property_portal_id"),
        Index("ix_property_location", "county", "municipality"),
        Index("ix_property_filters", "property_type", "price", "living_area", "land_area"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portal: Mapped[str] = mapped_column(String(50), index=True)
    portal_id: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str] = mapped_column(String(80), default="house")
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_per_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    living_area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    land_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    rooms: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    year: Mapped[int | None]
    city: Mapped[str | None] = mapped_column(String(150), index=True)
    municipality: Mapped[str | None] = mapped_column(String(150), index=True)
    county: Mapped[str | None] = mapped_column(String(150), index=True)
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    images: Mapped[str | None] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(String(250))
    phone: Mapped[str | None] = mapped_column(String(100))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    """An immutable listing price change."""

    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    new_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    property: Mapped[Property] = relationship(back_populates="price_history")
