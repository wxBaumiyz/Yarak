# SPDX-License-Identifier: MIT
"""Geschuetzte Reservierungs-Endpunkte unter /reservations/ (JWT erforderlich)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import service
from app.assets import AssetsClient
from app.auth import require_user
from app.dependencies import get_assets, get_session
from app.errors import ApiError
from app.etag import compute_etag, etag_matches
from app.routers.common import parse_json_body
from app.schemas import ReservationPrototype, ReservationReplacement, reservation_to_dict

router = APIRouter(prefix="/reservations", tags=["reservations"], dependencies=[Depends(require_user)])

BASE = "/api/v4/reservations"


@router.get("")
async def list_reservations(
    session: AsyncSession = Depends(get_session),
    include_deleted: str = "false",
    room_id: uuid.UUID | None = None,
    before: date | None = None,
    after: date | None = None,
) -> dict:
    # Spec: nur der Wert `true` inkludiert geloeschte; jeder andere Wert nicht.
    rows = await service.list_reservations(
        session, include_deleted=include_deleted == "true", room_id=room_id, before=before, after=after
    )
    return {"reservations": [reservation_to_dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_reservation(
    request: Request,
    session: AsyncSession = Depends(get_session),
    assets: AssetsClient = Depends(get_assets),
    user: dict = Depends(require_user),
) -> JSONResponse:
    proto = await parse_json_body(request, ReservationPrototype)
    reservation = await service.create_reservation(session, assets, proto, user.get("sub"))
    return JSONResponse(
        status_code=201,
        content=reservation_to_dict(reservation),
        headers={
            "Location": f"{BASE}/reservations/{reservation.id}",
            "ETag": compute_etag(reservation),
        },
    )


@router.get("/{reservation_id}")
async def get_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> Response:
    reservation = await service.get_reservation(session, reservation_id)
    if reservation is None:
        # 404-Code muss laut ErrorContainer-Enum der Spec einer der erlaubten Werte sein.
        raise ApiError(404, "deleted_reservation", f"The reservation `{reservation_id}` does not exist.")
    etag = compute_etag(reservation)
    if if_none_match is not None and etag_matches(if_none_match, etag):
        # Ressource seit dem letzten GET des Clients unveraendert -> 304 ohne Body
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(content=reservation_to_dict(reservation), headers={"ETag": etag})


@router.put("/{reservation_id}")
async def replace_reservation(
    request: Request,
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    assets: AssetsClient = Depends(get_assets),
    user: dict = Depends(require_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> JSONResponse:
    body = await parse_json_body(request, ReservationReplacement)
    reservation, created = await service.replace_reservation(session, assets, reservation_id, body, if_match, user.get("sub"))
    headers = {"ETag": compute_etag(reservation)}
    if created:
        headers["Location"] = f"{BASE}/reservations/{reservation.id}"
    return JSONResponse(status_code=201 if created else 200, content=reservation_to_dict(reservation), headers=headers)


@router.delete("/{reservation_id}", status_code=204)
async def delete_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_user),
    permanent: str = "false",
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> None:
    # Spec: nur `true` loescht endgueltig; jeder andere Wert ist ein Soft-Delete.
    await service.delete_reservation(session, reservation_id, permanent == "true", if_match, user.get("sub"))
    return None
