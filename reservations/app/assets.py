"""HTTP-Client fuer den assets-Service.

Raum-Existenz wird laut Aufgabenstellung ueber die assets-API geprueft
(GET /api/v3/assets/rooms/{id}), nie direkt ueber dessen Datenbank.
Der readiness-Check nutzt GET /api/v3/assets/health/live.
"""

from __future__ import annotations

import uuid

import httpx

from app.errors import ApiError


class AssetsClient:
    def __init__(self, base_url: str, prefix: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._prefix = prefix.rstrip("/")

    async def room_exists(self, room_id: uuid.UUID) -> bool:
        try:
            response = await self._client.get(f"{self._prefix}/rooms/{room_id}")
        except httpx.HTTPError as exc:
            raise ApiError(503, "room_not_found", f"assets-service nicht erreichbar: {exc}") from exc
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        raise ApiError(503, "room_not_found", f"assets-service antwortet mit HTTP {response.status_code}.")

    async def is_live(self) -> bool:
        """Liveness des assets-Service ueber dessen health/live-Endpunkt."""
        try:
            response = await self._client.get(f"{self._prefix}/health/live")
            return response.status_code == 200 and bool(response.json().get("live"))
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
