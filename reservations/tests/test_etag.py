# SPDX-License-Identifier: MIT
"""ETag-Conditional-Requests: If-None-Match auf GET -> 304, If-Match auf PUT/DELETE -> 412."""

from __future__ import annotations

from tests.conftest import BASE, prototype


async def _create(client, auth) -> tuple[str, str]:
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    assert resp.status_code == 201
    return resp.json()["id"], resp.headers["ETag"]


async def test_get_if_none_match_returns_304(client, auth):
    rid, etag = await _create(client, auth)
    resp = await client.get(f"{BASE}/reservations/{rid}", headers={**auth, "If-None-Match": etag})
    assert resp.status_code == 304
    assert resp.headers["ETag"] == etag
    assert resp.content == b""


async def test_get_if_none_match_mismatch_returns_200(client, auth):
    rid, _ = await _create(client, auth)
    resp = await client.get(f"{BASE}/reservations/{rid}", headers={**auth, "If-None-Match": '"stale"'})
    assert resp.status_code == 200
    assert resp.json()["id"] == rid


async def test_public_get_if_none_match_returns_304(client):
    resp = await client.post(f"{BASE}/public-reservations", json=prototype())
    assert resp.status_code == 201
    rid, etag = resp.json()["id"], resp.headers["ETag"]
    resp = await client.get(f"{BASE}/public-reservations/{rid}", headers={"If-None-Match": etag})
    assert resp.status_code == 304


async def test_etag_changes_after_put_and_then_304(client, auth):
    rid, etag = await _create(client, auth)
    resp = await client.put(
        f"{BASE}/reservations/{rid}",
        json=prototype(name="Anderer Name", to="2026-03-12"),
        headers={**auth, "If-Match": etag},
    )
    assert resp.status_code == 200
    new_etag = resp.headers["ETag"]
    assert new_etag != etag
    # neuer ETag liefert 304, der alte nicht mehr
    resp = await client.get(f"{BASE}/reservations/{rid}", headers={**auth, "If-None-Match": new_etag})
    assert resp.status_code == 304
    resp = await client.get(f"{BASE}/reservations/{rid}", headers={**auth, "If-None-Match": etag})
    assert resp.status_code == 200
