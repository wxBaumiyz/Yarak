# SPDX-License-Identifier: MIT
"""Async-DB-Engine, Session-Factory und Schema-Initialisierung."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


async def init_db(engine: AsyncEngine) -> None:
    """Legt die Tabelle an, falls sie noch nicht existiert (checkfirst)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_db(engine: AsyncEngine) -> bool:
    """Prueft die Datenbankverbindung fuer den readiness-Check."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
