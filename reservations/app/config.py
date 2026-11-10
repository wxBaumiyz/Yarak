# SPDX-License-Identifier: MIT
"""Konfiguration des reservations-Service, komplett ueber Umgebungsvariablen steuerbar.

Die Default-Werte passen zur Deployment-Umgebung aus biletado/kustomize
(base/backend/reservations/deployment.yaml).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    """Alle Konfigurationsparameter des Service."""

    # HTTP
    port: int = int(_env("PORT", "9000"))
    cors_allow_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in _env("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
    )

    # Logging
    log_level: str = _env("LOG_LEVEL", "INFO").upper()
    log_format: str = _env("LOG_FORMAT", "text").lower()  # "text" | "json"

    # Datenbank (POSTGRES_RESERVATIONS_* wie im kustomize-Deployment, DATABASE_URL als Override)
    database_url: str | None = os.environ.get("DATABASE_URL") or None
    postgres_host: str = _env("POSTGRES_RESERVATIONS_HOST", "localhost")
    postgres_port: int = int(_env("POSTGRES_RESERVATIONS_PORT", "5432"))
    postgres_user: str = _env("POSTGRES_RESERVATIONS_USER", "postgres")
    postgres_password: str = _env("POSTGRES_RESERVATIONS_PASSWORD", "postgres")
    postgres_dbname: str = _env("POSTGRES_RESERVATIONS_DBNAME", "reservations_v4")

    # assets-Service (Raum-Validierung + health/live)
    assets_api_host: str = _env("ASSETS_API_HOST", "http://assets").rstrip("/")
    assets_api_prefix: str = _env("ASSETS_API_PREFIX", "/api/v3/assets")
    assets_timeout_seconds: float = float(_env("ASSETS_TIMEOUT_SECONDS", "5"))

    # IAM / Keycloak (JWT-Signaturpruefung via JWKS)
    keycloak_scheme: str = _env("KEYCLOAK_SCHEME", "http")
    keycloak_host: str = _env("KEYCLOAK_HOST", "keycloak")
    keycloak_realm: str = _env("KEYCLOAK_REALM", "biletado")
    keycloak_path_prefix: str = _env("KEYCLOAK_PATH_PREFIX", "/auth")
    jwt_jwks_url: str | None = os.environ.get("JWT_JWKS_URL") or None
    jwt_jwks_json: str | None = os.environ.get("JWT_JWKS_JSON") or None  # inline JWKS z.B. fuer Tests
    jwt_issuer: str | None = os.environ.get("JWT_ISSUER") or None

    # Status-API
    api_version: str = _env("API_VERSION", "4.1.1")
    authors: list[str] = field(
        default_factory=lambda: [
            a.strip() for a in _env("AUTHORS", "yarak as rest api kubernetes").split(",") if a.strip()
        ]
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_dbname}"
        )

    @property
    def resolved_jwks_url(self) -> str | None:
        if self.jwt_jwks_url:
            return self.jwt_jwks_url
        prefix = self.keycloak_path_prefix.rstrip("/")
        return f"{self.keycloak_scheme}://{self.keycloak_host}{prefix}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


def load_settings() -> Settings:
    return Settings()
