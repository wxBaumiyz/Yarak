"""Gemeinsame Hilfsfunktionen der Router."""

from __future__ import annotations

import json

from fastapi import Request
from pydantic import BaseModel, ValidationError

from app.errors import ApiError


async def parse_json_body[ModelT: BaseModel](request: Request, model_cls: type[ModelT]) -> ModelT:
    """Parst den Request-Body und unterscheidet invalid_json (400) von schema_violation (400)."""
    raw = await request.body()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ApiError(400, "invalid_json", "The request body could not be parsed as JSON.", more_info=str(exc)) from exc
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ApiError(
            400, "schema_violation", "The request body does not match the required schema.", more_info=str(exc)
        ) from exc
