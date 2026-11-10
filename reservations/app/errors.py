"""Zentrales Error-Handling im Format des ErrorContainer-Schemas aus der OpenAPI-Spec."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Fachlicher Fehler, der als ErrorContainer geantwortet wird."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        more_info: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.more_info = more_info
        self.headers = headers or {}


def error_body(code: str, message: str, more_info: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if more_info:
        error["more_info"] = more_info
    return {"errors": [error], "trace": str(uuid.uuid4())}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.more_info),
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_body(
            "schema_violation",
            "The request does not match the required schema.",
            more_info=str(exc.errors()),
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=error_body("internal_error", "Unexpected server error."))
