# SPDX-License-Identifier: MIT
"""Status-Endpunkte: /status (ohne Auth) und /status/auth (mit Auth, HTTP 204)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.auth import require_user

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(request: Request) -> dict:
    settings = request.app.state.settings
    return {"authors": settings.authors, "api_version": settings.api_version}


@router.get("/status/auth", status_code=204, dependencies=[Depends(require_user)])
async def get_status_auth() -> Response:
    return Response(status_code=204)
