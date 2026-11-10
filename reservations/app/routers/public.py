"""Oeffentliche Endpunkte unter /public-reservations/ (nur lesend + anlegen, nie geloeschte)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import service
from app.assets import AssetsClient
from app.dependencies import get_assets, get_session
from app.errors import ApiError
from app.etag import compute_etag
from app.routers.common import parse_json_body
from app.schemas import ReservationPrototype, reservation_to_dict

router = APIRouter(prefix="/public-reservations", tags=["public-reservations"])

BASE = "/api/v4/reservations"


@router.get("")
async def list_public_reservations(
    session: AsyncSession = Depends(get_session),
    room_id: uuid.UUID | None = None,
    before: date | None = None,
    after: date | None = None,
) -> dict:
    rows = await service.list_reservations(
        session, include_deleted=False, room_id=room_id, before=before, after=after
    )
    return {"reservations": [reservation_to_dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_public_reservation(
    request: Request,
    session: AsyncSession = Depends(get_session),
    assets: AssetsClient = Depends(get_assets),
) -> JSONResponse:
    proto = await parse_json_body(request, ReservationPrototype)
    reservation = await service.create_reservation(session, assets, proto, user_id=None)
    return JSONResponse(
        status_code=201,
        content=reservation_to_dict(reservation),
        headers={
            "Location": f"{BASE}/public-reservations/{reservation.id}",
            "ETag": compute_etag(reservation),
        },
    )


@router.get("/{reservation_id}")
async def get_public_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    reservation = await service.get_reservation(session, reservation_id)
    if reservation is None or reservation.deleted_at is not None:
        # 404-Code muss laut ErrorContainer-Enum der Spec einer der erlaubten Werte sein.
        raise ApiError(404, "deleted_reservation", f"The reservation `{reservation_id}` does not exist or is deleted.")
    return JSONResponse(content=reservation_to_dict(reservation), headers={"ETag": compute_etag(reservation)})
