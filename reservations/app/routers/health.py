# SPDX-License-Identifier: MIT
"""Health-Endpunkte: /health, /health/live, /health/ready (ohne Auth).

/health/ready beruecksichtigt neben der DB-Verbindung die Liveness des
assets-Service (GET /health/live des assets-Service).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.assets import AssetsClient
from app.database import check_db
from app.dependencies import get_assets

router = APIRouter(tags=["status"])


async def _health_state(request: Request) -> dict:
    assets: AssetsClient = get_assets(request)
    db_ok = await check_db(request.app.state.engine)
    assets_live = await assets.is_live()
    return {
        "live": True,
        "ready": db_ok and assets_live,
        "databases": {"reservations": {"connected": db_ok}},
        "assets": {"live": assets_live},
    }


@router.get("/health")
async def get_health(request: Request) -> dict:
    return await _health_state(request)


@router.get("/health/live")
async def get_health_live() -> dict:
    return {"live": True}


@router.get("/health/ready")
async def get_health_ready(request: Request) -> JSONResponse:
    state = await _health_state(request)
    status = 200 if state["ready"] else 503
    return JSONResponse(status_code=status, content=state)
