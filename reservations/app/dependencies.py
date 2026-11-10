# SPDX-License-Identifier: MIT
"""FastAPI-Dependencies (DB-Session, assets-Client)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets import AssetsClient


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


def get_assets(request: Request) -> AssetsClient:
    return request.app.state.assets_client
