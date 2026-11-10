# SPDX-License-Identifier: MIT
"""FastAPI-App des reservations-v4-Backends.

Start lokal:  uvicorn app.main:app --port 9000
Konfiguration komplett ueber Umgebungsvariablen, siehe app/config.py und README.md.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.assets import AssetsClient
from app.auth import JwtVerifier
from app.config import Settings, load_settings
from app.database import create_engine, init_db, make_session_factory
from app.errors import ApiError, api_error_handler, unhandled_error_handler, validation_error_handler
from app.logging_conf import configure_logging, request_id_var
from app.routers import health, public, reservations, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(app.state.engine)
    yield
    await app.state.engine.dispose()
    await app.state.assets_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(title="biletado reservations", version=settings.api_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Setzt pro Request eine X-Request-ID (uebernimmt eine vorhandene) und loggt sie in jedem Eintrag mit."""
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    app.state.settings = settings
    app.state.engine = create_engine(settings.resolved_database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.state.assets_client = AssetsClient(settings.assets_api_host, settings.assets_api_prefix, settings.assets_timeout_seconds)
    jwks_url = settings.jwt_jwks_url or (None if settings.jwt_jwks_json else settings.resolved_jwks_url)
    app.state.jwt_verifier = JwtVerifier(jwks_url, settings.jwt_jwks_json, settings.jwt_issuer)

    base = "/api/v4/reservations"
    app.include_router(status.router, prefix=base)
    app.include_router(health.router, prefix=base)
    app.include_router(reservations.router, prefix=base)
    app.include_router(public.router, prefix=base)

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    return app


app = create_app()
