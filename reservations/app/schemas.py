"""Pydantic-Modelle passend zu den Schemas der OpenAPI-Spec reservations-v4."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Reservation

# Muster direkt aus der OpenAPI-Spec uebernommen
NAME_PATTERN = r"^([a-zA-ZäöüÄÖÜßĉĝĥĵŝŭĈĜĤIĴŜŬ0-9-.]+ )*([a-zA-ZäöüÄÖÜßĉĝĥĵŝŭĈĜĤIĴŜŬ0-9-.]+)$"
COMMENT_PATTERN = r"^([a-zA-ZäöüÄÖÜßĉĝĥĵŝŭĈĜĤIĴŜŬ0-9-.]+( [a-zA-ZäöüÄÖÜßĉĝĥĵŝŭĈĜĤIĴŜŬ0-9-.]+)*\n?)*$"


class ReservationPrototype(BaseModel):
    """Eingabedaten zum Anlegen/Ersetzen einer Reservierung."""

    # additionalProperties: false laut Spec; `comment` ist optional, aber nicht nullable
    # (Default None wird nicht validiert, ein explizites null im Body schon).
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, min_length=1)
    comment: str = Field(default=None, pattern=COMMENT_PATTERN, max_length=2048)
    from_: date = Field(alias="from")
    to_: date = Field(alias="to")
    room_id: uuid.UUID


class ReservationReplacement(ReservationPrototype):
    """PUT-Body: Prototype + optional `deleted_at: null` zum Wiederherstellen."""

    deleted_at: None = None


def format_rfc3339(dt: datetime) -> str:
    """RFC3339/ISO-8601 mit Z-Suffix fuer UTC, wie in den Spec-Beispielen (naive Werte = UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def reservation_to_dict(r: Reservation) -> dict:
    """Serialisiert eine Reservierung; optionale Felder werden bei None weggelassen."""
    data: dict = {
        "id": str(r.id),
        "name": r.name,
        "from": r.from_.isoformat(),
        "to": r.to_.isoformat(),
        "room_id": str(r.room_id),
    }
    if r.comment is not None:
        data["comment"] = r.comment
    if r.deleted_at is not None:
        data["deleted_at"] = format_rfc3339(r.deleted_at)
    return data
