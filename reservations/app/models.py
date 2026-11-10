"""SQLAlchemy-ORM-Modell der reservations-Tabelle (Schema siehe kustomize 200_reservations-v4.sql)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_: Mapped[date] = mapped_column("from", Date, nullable=False)
    to_: Mapped[date] = mapped_column("to", Date, nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
