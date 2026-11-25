from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"detail": {"code": code, "message": message}}


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message),
        headers=exc.headers,
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    message = "Request parameters are invalid."
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        detail = first.get("msg", message)
        message = f"{location}: {detail}" if location else detail
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", message),
    )


async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_body(
            "INTERNAL_ERROR", "An unexpected server error occurred."
        ),
    )
