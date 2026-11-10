# SPDX-License-Identifier: MIT
"""Tests der oeffentlichen API ohne Authentifizierung: /status, /public-reservations/."""

from __future__ import annotations

from tests.conftest import BASE, ROOM_A, ROOM_B, ROOM_UNKNOWN, prototype


async def test_status_without_auth(client):
    resp = await client.get(f"{BASE}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_version"] == "4.1.1"
    assert len(body["authors"]) >= 1


async def test_public_list_empty(client):
    resp = await client.get(f"{BASE}/public-reservations")
    assert resp.status_code == 200
    assert resp.json() == {"reservations": []}


async def test_public_create_and_get(client):
    resp = await client.post(f"{BASE}/public-reservations", json=prototype())
    assert resp.status_code == 201
    assert resp.headers["Location"].endswith(f"/public-reservations/{resp.json()['id']}")
    assert "ETag" in resp.headers
    body = resp.json()
    assert body["name"] == "Max Mustermann"
    assert body["room_id"] == str(ROOM_A)
    assert "deleted_at" not in body

    resp = await client.get(f"{BASE}/public-reservations")
    assert len(resp.json()["reservations"]) == 1

    resp = await client.get(f"{BASE}/public-reservations/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == body["id"]


async def test_public_create_invalid_json(client):
    resp = await client.post(
        f"{BASE}/public-reservations", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_json"


async def test_public_create_schema_violation(client):
    body = prototype()
    del body["name"]
    resp = await client.post(f"{BASE}/public-reservations", json=body)
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "schema_violation"


async def test_public_create_invalid_date_range(client):
    for from_, to in [("2026-03-10", "2026-03-10"), ("2026-03-11", "2026-03-10")]:
        resp = await client.post(f"{BASE}/public-reservations", json=prototype(from_=from_, to=to))
        assert resp.status_code == 400
        assert resp.json()["errors"][0]["code"] == "invalid_date_range"


async def test_public_create_room_not_found(client):
    resp = await client.post(f"{BASE}/public-reservations", json=prototype(room_id=ROOM_UNKNOWN))
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "room_not_found"


async def test_public_create_overlap_conflict_and_touching(client):
    resp = await client.post(f"{BASE}/public-reservations", json=prototype(from_="2026-03-10", to="2026-03-15"))
    assert resp.status_code == 201

    # echte Ueberlappung -> 409
    resp = await client.post(f"{BASE}/public-reservations", json=prototype(from_="2026-03-12", to="2026-03-20"))
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "overlapping_reservation"

    # angrenzend (to == from) ueberlappt nicht -> 201
    resp = await client.post(f"{BASE}/public-reservations", json=prototype(from_="2026-03-15", to="2026-03-20"))
    assert resp.status_code == 201

    # anderer Raum darf ueberlappen -> 201
    resp = await client.post(f"{BASE}/public-reservations", json=prototype(room_id=ROOM_B, from_="2026-03-10", to="2026-03-15"))
    assert resp.status_code == 201


async def test_public_get_unknown_is_404(client):
    import uuid

    resp = await client.get(f"{BASE}/public-reservations/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_public_filters(client):
    await client.post(f"{BASE}/public-reservations", json=prototype(room_id=ROOM_A, from_="2026-03-10", to="2026-03-15"))
    await client.post(f"{BASE}/public-reservations", json=prototype(room_id=ROOM_B, from_="2026-03-20", to="2026-03-25"))

    resp = await client.get(f"{BASE}/public-reservations", params={"room_id": str(ROOM_A)})
    assert [r["room_id"] for r in resp.json()["reservations"]] == [str(ROOM_A)]

    resp = await client.get(f"{BASE}/public-reservations", params={"before": "2026-03-16"})
    assert len(resp.json()["reservations"]) == 1  # from < before

    resp = await client.get(f"{BASE}/public-reservations", params={"after": "2026-03-19"})
    assert len(resp.json()["reservations"]) == 1  # to > after

    # after < to UND before > from: Reservierung B (03-20..03-25) schneidet das Fenster 03-16..03-24
    resp = await client.get(f"{BASE}/public-reservations", params={"after": "2026-03-16", "before": "2026-03-24"})
    rooms = [r["room_id"] for r in resp.json()["reservations"]]
    assert rooms == [str(ROOM_B)]
