"""One error shape for every non-2xx response, plus a request id for tracing."""
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    default_message = "Bad request"

    def __init__(self, message: str | None = None, *, details=None):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.details = details


class UnauthorizedError(AppError):
    status_code, code, default_message = 401, "unauthorized", "Authentication required"


class ForbiddenError(AppError):
    status_code, code, default_message = 403, "forbidden", "Not allowed"


class NotFoundError(AppError):
    status_code, code, default_message = 404, "not_found", "Not found"


class ConflictError(AppError):
    status_code, code, default_message = 409, "conflict", "Conflict"


_HTTP_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
               405: "method_not_allowed", 409: "conflict", 429: "rate_limited"}


def _body(request: Request, code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details,
                      "requestId": getattr(request.state, "request_id", None)}}


class RequestIdMiddleware:
    """Pure ASGI middleware (not BaseHTTPMiddleware) so it never buffers streaming/SSE responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode())]
            await send(message)

        await self.app(scope, receive, send_with_id)


def error_response(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status_code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Report field + message only. FastAPI's default echoes the submitted value, which could be a password.
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body(request, "validation_error", "Invalid request", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return JSONResponse(_body(request, code, str(exc.detail)), status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Never leak internals to the client; the request id lets us find the traceback in the logs.
        return JSONResponse(_body(request, "internal_error", "Something went wrong"), status_code=500)
