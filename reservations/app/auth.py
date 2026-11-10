"""JWT-Authentifizierung gegen das IAM (Keycloak) der Umgebung.

Geprueft wird die Signatur des Tokens ueber die JWKS des Realms sowie die
Gueltigkeit (exp/nbf). Scopes/Autorisierung werden laut Aufgabenstellung nicht
geprueft. User-Id fuer das Audit-Logging ist das `sub`-Claim.
"""

from __future__ import annotations

import json

import jwt
from fastapi import Request
from jwt import PyJWK, PyJWKClient

from app.errors import ApiError

WWW_AUTHENTICATE = 'Bearer realm="biletado"'
SUPPORTED_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]


class JwtVerifier:
    """Verifiziert Bearer-Tokens gegen JWKS (URL oder inline als JSON)."""

    def __init__(
        self,
        jwks_url: str | None = None,
        jwks_json: str | None = None,
        issuer: str | None = None,
    ) -> None:
        self._issuer = issuer
        self._client: PyJWKClient | None = PyJWKClient(jwks_url) if jwks_url else None
        self._keys: list[PyJWK] = []
        if jwks_json:
            jwks = json.loads(jwks_json)
            self._keys = [PyJWK.from_dict(key) for key in jwks.get("keys", [])]

    def _signing_key(self, kid: str | None):
        if self._client is not None:
            return self._client.get_signing_key(kid).key
        for key in self._keys:
            if kid is None or key.key_id == kid:
                return key.key
        raise jwt.PyJWKError("no matching key in JWKS")

    def verify(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            key = self._signing_key(header.get("kid"))
            return jwt.decode(
                token,
                key,
                algorithms=SUPPORTED_ALGORITHMS,
                options={"verify_aud": False},
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise ApiError(
                401,
                "not_authorized",
                f"Invalid or expired token: {exc}",
                headers={"WWW-Authenticate": f'{WWW_AUTHENTICATE}, error="invalid_token"'},
            ) from exc


async def require_user(request: Request) -> dict:
    """FastAPI-Dependency: verlangt einen gueltigen JWT und liefert dessen Claims."""
    verifier: JwtVerifier = request.app.state.jwt_verifier
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise ApiError(401, "not_authorized", "Missing bearer token.", headers={"WWW-Authenticate": WWW_AUTHENTICATE})
    token = header[7:].strip()
    if not token:
        raise ApiError(401, "not_authorized", "Missing bearer token.", headers={"WWW-Authenticate": WWW_AUTHENTICATE})
    return verifier.verify(token)
