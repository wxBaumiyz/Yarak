"""Fachlogik der Reservierungen (DB-Zugriff, Validierung, Overlap-Pruefung, Audit-Logging)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets import AssetsClient
from app.errors import ApiError
from app.etag import compute_etag, etag_matches
from app.models import Reservation
from app.schemas import ReservationPrototype, ReservationReplacement

audit_logger = logging.getLogger("app.audit")


def _audit(operation: str, reservation_id: uuid.UUID, user_id: str | None) -> None:
    """Loggt nicht-lesende Operationen mit Operation, Objekttyp, Objekt-Id und User-Id."""
    audit_logger.info(
        "operation=%s object_type=reservation object_id=%s user_id=%s",
        operation,
        reservation_id,
        user_id or "anonymous",
        extra={"operation": operation, "object_type": "reservation", "object_id": str(reservation_id), "user_id": user_id},
    )


def validate_date_range(proto: ReservationPrototype) -> None:
    if not proto.from_ < proto.to_:
        raise ApiError(400, "invalid_date_range", "`from` must be strictly before `to`.")


async def find_overlap(
    session: AsyncSession,
    room_id: uuid.UUID,
    from_: date,
    to_: date,
    exclude_id: uuid.UUID | None = None,
) -> Reservation | None:
    """Sucht eine nicht geloeschte, ueberlappende Reservierung desselben Raums.

    Angrenzende Reservierungen (to == from) ueberlappen nicht.
    """
    stmt = select(Reservation).where(
        Reservation.room_id == room_id,
        Reservation.deleted_at.is_(None),
        Reservation.from_ < to_,
        from_ < Reservation.to_,
    )
    if exclude_id is not None:
        stmt = stmt.where(Reservation.id != exclude_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def validate_room(assets: AssetsClient, room_id: uuid.UUID) -> None:
    if not await assets.room_exists(room_id):
        raise ApiError(400, "room_not_found", f"The room `{room_id}` does not exist.")


async def list_reservations(
    session: AsyncSession,
    *,
    include_deleted: bool,
    room_id: uuid.UUID | None,
    before: date | None,
    after: date | None,
) -> list[Reservation]:
    stmt = select(Reservation)
    if not include_deleted:
        stmt = stmt.where(Reservation.deleted_at.is_(None))
    if room_id is not None:
        stmt = stmt.where(Reservation.room_id == room_id)
    if before is not None:
        stmt = stmt.where(Reservation.from_ < before)
    if after is not None:
        stmt = stmt.where(Reservation.to_ > after)
    stmt = stmt.order_by(Reservation.from_, Reservation.to_, Reservation.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_reservation(session: AsyncSession, reservation_id: uuid.UUID) -> Reservation | None:
    return await session.get(Reservation, reservation_id)


async def create_reservation(
    session: AsyncSession,
    assets: AssetsClient,
    proto: ReservationPrototype,
    user_id: str | None,
    reservation_id: uuid.UUID | None = None,
) -> Reservation:
    validate_date_range(proto)
    await validate_room(assets, proto.room_id)
    overlap = await find_overlap(session, proto.room_id, proto.from_, proto.to_)
    if overlap is not None:
        raise ApiError(
            409,
            "overlapping_reservation",
            f"The room `{proto.room_id}` is already reserved from `{overlap.from_}` to `{overlap.to_}`.",
        )
    reservation = Reservation(
        id=reservation_id or uuid.uuid4(),
        name=proto.name,
        comment=proto.comment,
        from_=proto.from_,
        to_=proto.to_,
        room_id=proto.room_id,
    )
    session.add(reservation)
    await session.commit()
    await session.refresh(reservation)
    _audit("create", reservation.id, user_id)
    return reservation


async def replace_reservation(
    session: AsyncSession,
    assets: AssetsClient,
    reservation_id: uuid.UUID,
    body: ReservationReplacement,
    if_match: str | None,
    user_id: str | None,
) -> tuple[Reservation, bool]:
    """Ersetzt bzw. erstellt eine Reservierung. Rueckgabe: (Reservierung, created)."""
    validate_date_range(body)
    existing = await get_reservation(session, reservation_id)
    if existing is None:
        if if_match is not None:
            raise ApiError(412, "etag_mismatch", "The given `If-Match` header does not match the current `ETag` of the reservation.")
        reservation = await create_reservation(session, assets, body, user_id, reservation_id=reservation_id)
        return reservation, True

    if if_match is not None and not etag_matches(if_match, compute_etag(existing)):
        raise ApiError(412, "etag_mismatch", "The given `If-Match` header does not match the current `ETag` of the reservation.")
    # `deleted_at` darf laut Schema nur null sein; ob das Feld ueberhaupt gesetzt war,
    # steht in model_fields_set (nur dann wird wiederhergestellt)
    restore_requested = "deleted_at" in body.model_fields_set
    if existing.deleted_at is not None and not restore_requested:
        raise ApiError(
            409,
            "deleted_reservation",
            f"The reservation `{reservation_id}` is deleted. Set `deleted_at: null` to restore it.",
        )
    await validate_room(assets, body.room_id)
    overlap = await find_overlap(session, body.room_id, body.from_, body.to_, exclude_id=reservation_id)
    if overlap is not None:
        raise ApiError(
            409,
            "overlapping_reservation",
            f"The room `{body.room_id}` is already reserved from `{overlap.from_}` to `{overlap.to_}`.",
        )

    existing.name = body.name
    existing.comment = body.comment
    existing.from_ = body.from_
    existing.to_ = body.to_
    existing.room_id = body.room_id
    if restore_requested:
        existing.deleted_at = None  # Wiederherstellen
    await session.commit()
    await session.refresh(existing)
    _audit("replace", existing.id, user_id)
    return existing, False


async def delete_reservation(
    session: AsyncSession,
    reservation_id: uuid.UUID,
    permanent: bool,
    if_match: str | None,
    user_id: str | None,
) -> None:
    existing = await get_reservation(session, reservation_id)
    if existing is None:
        raise ApiError(404, "deleted_reservation", f"The reservation `{reservation_id}` does not exist.")
    if if_match is not None and not etag_matches(if_match, compute_etag(existing)):
        raise ApiError(412, "etag_mismatch", "The given `If-Match` header does not match the current `ETag` of the reservation.")
    if permanent:
        # endgueltiges Loeschen funktioniert auch bei bereits soft-geloeschten Reservierungen
        await session.delete(existing)
        operation = "delete_permanent"
    elif existing.deleted_at is not None:
        raise ApiError(404, "deleted_reservation", f"The reservation `{reservation_id}` is already deleted.")
    else:
        existing.deleted_at = datetime.now(UTC)
        operation = "delete"
    await session.commit()
    _audit(operation, reservation_id, user_id)
