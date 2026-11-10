"""ETag-Berechnung fuer Optimistic Concurrency Control (If-Match)."""

from __future__ import annotations

import hashlib

from app.models import Reservation


def compute_etag(r: Reservation) -> str:
    """Stabiler ETag aus dem gesamten fachlichen Inhalt der Reservierung.

    Als schwacher Validator (W/...) formatiert: Der Envoy-Proxy deriletado-Umgebung
    komprimiert Antworten (gzip) und entfernt dabei starke ETags; schwache bleiben erhalten.
    """
    payload = "|".join(
        [
            str(r.id),
            r.name,
            r.comment or "",
            r.from_.isoformat(),
            r.to_.isoformat(),
            str(r.room_id),
            r.deleted_at.isoformat() if r.deleted_at else "",
        ]
    )
    return 'W/"' + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32] + '"'


def etag_matches(header_value: str, current_etag: str) -> bool:
    """Vergleicht einen If-Match-Header mit dem aktuellen ETag (ignoriert W/-Praefix und Quotes)."""

    def normalize(value: str) -> str:
        value = value.strip()
        if value.startswith("W/"):
            value = value[2:]
        return value.strip('"')

    return normalize(header_value) == normalize(current_etag)
