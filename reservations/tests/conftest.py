"""Test-Fixtures: App mit sqlite-DB, Fake-assets-Service und lokalem RSA-JWKS."""

from __future__ import annotations

import json
import time
import uuid

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import Settings
from app.database import init_db
from app.main import create_app

BASE = "/api/v4/reservations"

ROOM_A = uuid.uuid4()  # existiert im Fake-assets-Service
ROOM_B = uuid.uuid4()  # existiert im Fake-assets-Service
ROOM_UNKNOWN = uuid.uuid4()  # existiert nicht


class FakeAssets:
    def __init__(self, rooms: set[uuid.UUID], live: bool = True) -> None:
        self.rooms = set(rooms)
        self.live = live

    async def room_exists(self, room_id: uuid.UUID) -> bool:
        return room_id in self.rooms

    async def is_live(self) -> bool:
        return self.live

    async def aclose(self) -> None:
        pass


def make_key_pair(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    public_jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return private, {"keys": [public_jwk]}


def make_token(private, kid: str, sub: str = "user-1", exp_offset: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": sub, "iat": now, "exp": now + exp_offset}
    return pyjwt.encode(payload, private, algorithm="RS256", headers={"kid": kid})


def prototype(room_id: uuid.UUID = ROOM_A, from_: str = "2026-03-10", to: str = "2026-03-11", **overrides) -> dict:
    body = {"name": "Max Mustermann", "comment": "I want only red pillows", "from": from_, "to": to, "room_id": str(room_id)}
    body.update(overrides)
    return body


@pytest.fixture
async def app(tmp_path):
    private, jwks = make_key_pair("test-key-1")
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        jwt_jwks_json=json.dumps(jwks),
        assets_api_host="http://assets.test",
    )
    application = create_app(settings)
    await init_db(application.state.engine)
    application.state.assets_client = FakeAssets({ROOM_A, ROOM_B})
    application.state.test_private_key = private
    application.state.test_kid = "test-key-1"
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def token(app) -> str:
    return make_token(app.state.test_private_key, app.state.test_kid)


@pytest.fixture
def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}
