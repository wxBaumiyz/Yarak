# SPDX-License-Identifier: MIT
"""Tests der JWT-Authentifizierung: /status/auth und geschuetzte /reservations/-Endpunkte."""

from __future__ import annotations

import time

import jwt as pyjwt

from tests.conftest import BASE, make_key_pair, make_token, prototype


async def test_status_auth_without_token_is_401(client):
    resp = await client.get(f"{BASE}/status/auth")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert resp.headers["WWW-Authenticate"].startswith("Bearer")
    assert resp.json()["errors"][0]["code"] == "not_authorized"


async def test_status_auth_with_garbage_token_is_401(client):
    resp = await client.get(f"{BASE}/status/auth", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "not_authorized"


async def test_status_auth_with_valid_token_is_204(client, token):
    resp = await client.get(f"{BASE}/status/auth", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204


async def test_status_auth_with_expired_token_is_401(client, app):
    expired = make_token(app.state.test_private_key, app.state.test_kid, exp_offset=-10)
    resp = await client.get(f"{BASE}/status/auth", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_status_auth_with_wrong_signature_is_401(client):
    other_private, other_jwks = make_key_pair("other-key")
    forged = pyjwt.encode(
        {"sub": "attacker", "iat": int(time.time()), "exp": int(time.time()) + 3600},
        other_private,
        algorithm="RS256",
        headers={"kid": "test-key-1"},  # behauptet, derselbe Key zu sein
    )
    resp = await client.get(f"{BASE}/status/auth", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_reservations_endpoints_require_auth(client):
    for method, path in [
        ("GET", f"{BASE}/reservations"),
        ("POST", f"{BASE}/reservations"),
        ("GET", f"{BASE}/reservations/00000000-0000-0000-0000-000000000000"),
        ("PUT", f"{BASE}/reservations/00000000-0000-0000-0000-000000000000"),
        ("DELETE", f"{BASE}/reservations/00000000-0000-0000-0000-000000000000"),
    ]:
        resp = await client.request(method, path, json=prototype() if method in ("POST", "PUT") else None)
        assert resp.status_code == 401, f"{method} {path}"
        assert "WWW-Authenticate" in resp.headers


async def test_reservations_list_with_valid_token(client, auth):
    resp = await client.get(f"{BASE}/reservations", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"reservations": []}


async def test_public_endpoints_stay_open(client):
    assert (await client.get(f"{BASE}/public-reservations")).status_code == 200
    assert (await client.get(f"{BASE}/status")).status_code == 200
    assert (await client.get(f"{BASE}/health/live")).status_code == 200
