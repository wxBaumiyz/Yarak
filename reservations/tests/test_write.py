"""Tests der schreibenden Endpunkte unter /reservations/ (mit JWT): CRUD, 409/412, ETag."""

from __future__ import annotations

import uuid

from tests.conftest import BASE, ROOM_B, prototype


async def _create(client, auth, **kwargs) -> dict:
    resp = await client.post(f"{BASE}/reservations", json=prototype(**kwargs), headers=auth)
    assert resp.status_code == 201
    return resp


async def test_create_get_list_with_auth(client, auth):
    resp = await _create(client, auth)
    rid = resp.json()["id"]
    assert resp.headers["Location"].endswith(f"/reservations/{rid}")
    etag = resp.headers["ETag"]

    resp = await client.get(f"{BASE}/reservations/{rid}", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["ETag"] == etag

    resp = await client.get(f"{BASE}/reservations", headers=auth)
    assert len(resp.json()["reservations"]) == 1


async def test_get_unknown_is_404(client, auth):
    resp = await client.get(f"{BASE}/reservations/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404


async def test_put_replace_and_etag(client, auth):
    created = await _create(client, auth)
    rid = created.json()["id"]
    etag = created.headers["ETag"]

    resp = await client.put(
        f"{BASE}/reservations/{rid}",
        json=prototype(from_="2026-04-01", to="2026-04-05", comment="changed"),
        headers={**auth, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["from"] == "2026-04-01"
    assert resp.headers["ETag"] != etag

    # falsches If-Match -> 412
    resp = await client.put(
        f"{BASE}/reservations/{rid}",
        json=prototype(from_="2026-05-01", to="2026-05-05"),
        headers={**auth, "If-Match": '"deadbeef"'},
    )
    assert resp.status_code == 412
    assert resp.json()["errors"][0]["code"] == "etag_mismatch"


async def test_put_creates_when_missing(client, auth):
    rid = uuid.uuid4()
    resp = await client.put(f"{BASE}/reservations/{rid}", json=prototype(), headers=auth)
    assert resp.status_code == 201
    assert resp.headers["Location"].endswith(f"/reservations/{rid}")
    assert resp.json()["id"] == str(rid)


async def test_put_overlap_is_409(client, auth):
    await _create(client, auth, from_="2026-03-10", to="2026-03-15")
    other = uuid.uuid4()
    resp = await client.put(
        f"{BASE}/reservations/{other}", json=prototype(from_="2026-03-14", to="2026-03-20"), headers=auth
    )
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "overlapping_reservation"


async def test_soft_delete_hide_restore_permanent(client, auth):
    created = await _create(client, auth)
    rid = created.json()["id"]
    etag = created.headers["ETag"]

    # soft delete
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers={**auth, "If-Match": etag})
    assert resp.status_code == 204

    # auth-List ohne include_deleted: weg; mit include_deleted: deleted_at gesetzt
    resp = await client.get(f"{BASE}/reservations", headers=auth)
    assert resp.json()["reservations"] == []
    resp = await client.get(f"{BASE}/reservations", params={"include_deleted": "true"}, headers=auth)
    items = resp.json()["reservations"]
    assert len(items) == 1 and "deleted_at" in items[0]

    # einzelner auth-Zugriff zeigt deleted_at, public 404
    resp = await client.get(f"{BASE}/reservations/{rid}", headers=auth)
    assert resp.status_code == 200 and "deleted_at" in resp.json()
    resp = await client.get(f"{BASE}/public-reservations/{rid}")
    assert resp.status_code == 404

    # erneutes DELETE -> 404
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers=auth)
    assert resp.status_code == 404

    # PUT auf geloeschte ohne deleted_at:null -> 409 deleted_reservation
    resp = await client.put(f"{BASE}/reservations/{rid}", json=prototype(), headers=auth)
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "deleted_reservation"

    # PUT mit deleted_at:null stellt wieder her
    resp = await client.put(f"{BASE}/reservations/{rid}", json={**prototype(), "deleted_at": None}, headers=auth)
    assert resp.status_code == 200
    assert "deleted_at" not in resp.json()

    # jetzt kollidiert eine neue Reservierung im selben Zeitraum -> 409
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    assert resp.status_code == 409

    # permanent delete
    resp = await client.delete(f"{BASE}/reservations/{rid}", params={"permanent": "true"}, headers=auth)
    assert resp.status_code == 204
    resp = await client.get(f"{BASE}/reservations/{rid}", headers=auth)
    assert resp.status_code == 404
    resp = await client.get(f"{BASE}/reservations", params={"include_deleted": "true"}, headers=auth)
    assert resp.json()["reservations"] == []


async def test_delete_if_match_mismatch_is_412(client, auth):
    created = await _create(client, auth)
    rid = created.json()["id"]
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers={**auth, "If-Match": '"nope"'})
    assert resp.status_code == 412
    # ohne If-Match geht es unveraendert
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers=auth)
    assert resp.status_code == 204


async def test_soft_deleted_does_not_block_room(client, auth):
    created = await _create(client, auth, room_id=ROOM_B, from_="2026-03-10", to="2026-03-15")
    rid = created.json()["id"]
    await client.delete(f"{BASE}/reservations/{rid}", headers=auth)
    # gleicher Zeitraum im selben Raum ist nach Soft-Delete wieder frei
    resp = await client.post(
        f"{BASE}/reservations", json=prototype(room_id=ROOM_B, from_="2026-03-10", to="2026-03-15"), headers=auth
    )
    assert resp.status_code == 201


async def test_write_validation_errors(client, auth):
    resp = await client.post(
        f"{BASE}/reservations", content=b"{broken", headers={**auth, "Content-Type": "application/json"}
    )
    assert resp.status_code == 400 and resp.json()["errors"][0]["code"] == "invalid_json"

    resp = await client.post(f"{BASE}/reservations", json=prototype(from_="2026-03-10", to="2026-03-09"), headers=auth)
    assert resp.status_code == 400 and resp.json()["errors"][0]["code"] == "invalid_date_range"

    resp = await client.post(f"{BASE}/reservations", json=prototype(name=""), headers=auth)
    assert resp.status_code == 400 and resp.json()["errors"][0]["code"] == "schema_violation"
