# SPDX-License-Identifier: MIT
"""Audit-Logging: User-Aktionen (create/replace/delete) und abgelehnte Schreibzugriffe werden geloggt."""

from __future__ import annotations

import logging

import pytest

from app.logging_conf import RequestIdFilter, request_id_var
from tests.conftest import BASE, ROOM_A, prototype


class _ListHandler(logging.Handler):
    def __init__(self, records: list) -> None:
        super().__init__(level=logging.INFO)
        self.records = records

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def audit_records():
    records: list[logging.LogRecord] = []
    handler = _ListHandler(records)
    logger = logging.getLogger("app.audit")
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


async def test_create_is_audit_logged_with_user_and_details(client, auth, audit_records):
    resp = await client.post(f"{BASE}/reservations", json=prototype(room_id=ROOM_A), headers=auth)
    assert resp.status_code == 201
    rid = resp.json()["id"]
    creates = [r for r in audit_records if r.__dict__.get("operation") == "create"]
    assert len(creates) == 1
    rec = creates[0]
    assert rec.__dict__["user_id"] == "user-1"
    assert rec.__dict__["object_id"] == rid
    details = rec.__dict__["details"]
    assert details["room_id"] == str(ROOM_A)
    assert details["name"] == "Max Mustermann"
    assert details["from"] == "2026-03-10"
    assert "user_id=user-1" in rec.getMessage()
    assert f"object_id={rid}" in rec.getMessage()


async def test_replace_logs_changed_fields(client, auth, audit_records):
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    rid, etag = resp.json()["id"], resp.headers["ETag"]
    resp = await client.put(
        f"{BASE}/reservations/{rid}",
        json=prototype(name="Neu", to="2026-03-20"),
        headers={**auth, "If-Match": etag},
    )
    assert resp.status_code == 200
    replaces = [r for r in audit_records if r.__dict__.get("operation") == "replace"]
    assert len(replaces) == 1
    changes = replaces[0].__dict__["details"]["changes"]
    assert changes["name"] == ["Max Mustermann", "Neu"]
    assert changes["to"] == ["2026-03-11", "2026-03-20"]


async def test_delete_is_audit_logged(client, auth, audit_records):
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    rid, etag = resp.json()["id"], resp.headers["ETag"]
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers={**auth, "If-Match": etag})
    assert resp.status_code == 204
    deletes = [r for r in audit_records if r.__dict__.get("operation") == "delete"]
    assert len(deletes) == 1
    assert deletes[0].__dict__["details"] == {"permanent": False}
    assert deletes[0].__dict__["user_id"] == "user-1"


async def test_denied_write_is_audit_logged(client, auth, audit_records):
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    rid = resp.json()["id"]
    resp = await client.delete(f"{BASE}/reservations/{rid}", headers={**auth, "If-Match": '"wrong"'})
    assert resp.status_code == 412
    denied = [r for r in audit_records if r.__dict__.get("operation") == "denied"]
    assert len(denied) == 1
    assert denied[0].levelno == logging.WARNING
    assert denied[0].__dict__["code"] == "etag_mismatch"
    assert denied[0].__dict__["user_id"] == "user-1"
    assert denied[0].__dict__["status"] == 412


async def test_public_create_logs_anonymous(client, audit_records):
    resp = await client.post(f"{BASE}/public-reservations", json=prototype())
    assert resp.status_code == 201
    creates = [r for r in audit_records if r.__dict__.get("operation") == "create"]
    assert len(creates) == 1
    assert creates[0].__dict__["user_id"] == "anonymous"


async def test_request_id_header_set_and_echoed(client, auth):
    resp = await client.post(f"{BASE}/reservations", json=prototype(), headers=auth)
    assert resp.status_code == 201
    assert resp.headers["X-Request-ID"]
    resp2 = await client.get(f"{BASE}/status", headers={"X-Request-ID": "my-id-123"})
    assert resp2.headers["X-Request-ID"] == "my-id-123"


def test_request_id_filter_sets_record_attribute():
    token = request_id_var.set("req-42")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
        RequestIdFilter().filter(record)
        assert record.request_id == "req-42"
    finally:
        request_id_var.reset(token)
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-"
