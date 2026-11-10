# SPDX-License-Identifier: MIT
"""Tests der health-Endpunkte inkl. assets-Liveness im readiness-Check."""

from __future__ import annotations

from tests.conftest import BASE, ROOM_A, FakeAssets


async def test_health_live(client):
    resp = await client.get(f"{BASE}/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"live": True}


async def test_health_ready_when_deps_ok(client):
    resp = await client.get(f"{BASE}/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["assets"]["live"] is True


async def test_health_summary(client):
    resp = await client.get(f"{BASE}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["live"] is True
    assert body["ready"] is True
    assert body["databases"]["reservations"]["connected"] is True


async def test_health_ready_503_when_assets_down(client, app):
    app.state.assets_client = FakeAssets({ROOM_A}, live=False)
    resp = await client.get(f"{BASE}/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert body["assets"]["live"] is False
