import json
import logging
import re
import secrets
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)

_INBOUND_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)([?&](?:api[_-]?key|insttoken|access[_-]?token)=)[^&\s\"'#]+"),
    re.compile(r"kv(?:mcp_(?:ac|at|rt)|1)_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?m)^(DETAIL:\s*).+$"),
)
SECRET_PATH_PARAMS = frozenset({"token"})
REDACTED = "[redacted]"

_STANDARD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


def redact_secrets(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + REDACTED, redacted)
    return redacted


def logged_path(scope: Scope) -> str | None:
    path = scope.get("path")
    params = scope.get("path_params") or {}
    hidden = {str(value) for name, value in params.items() if name in SECRET_PATH_PARAMS}
    if path is None or not hidden:
        return path
    return "/".join(REDACTED if part in hidden else part for part in path.split("/"))


def current_request_id() -> str | None:
    return _request_id.get()


def set_log_user(user_id: str | None) -> None:
    _user_id.set(user_id)


def new_request_id() -> str:
    return secrets.token_hex(12)


@contextmanager
def request_id_scope(request_id: str) -> Iterator[str]:
    if not _INBOUND_REQUEST_ID.fullmatch(request_id):
        raise ValueError("A request id is 8 to 64 letters, digits, dots, dashes or underscores")
    token = _request_id.set(request_id)
    try:
        yield request_id
    finally:
        _request_id.reset(token)


@contextmanager
def kept_request_id(prefix: str) -> Iterator[str]:
    found = current_request_id()
    if found is not None:
        yield found
        return
    with request_id_scope(f"{prefix}-{new_request_id()}") as made:
        yield made


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
        }
        request_id = _request_id.get()
        if request_id:
            payload["requestId"] = request_id
        user_id = _user_id.get()
        if user_id:
            payload["userId"] = user_id
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = (
                value if isinstance(value, int | float | bool | type(None)) else redact_secrets(str(value))
            )
        if record.exc_info:
            payload["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("kalavigyan.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        inbound = ""
        for name, value in scope.get("headers") or ():
            if name.lower() == REQUEST_ID_HEADER.lower().encode():
                inbound = value.decode("latin-1")
                break
        request_id = inbound if _INBOUND_REQUEST_ID.fullmatch(inbound) else new_request_id()
        token = _request_id.set(request_id)
        user_token = _user_id.set(None)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            self.logger.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": logged_path(scope),
                    "status": status_holder["status"],
                    "durationMs": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            _user_id.reset(user_token)
            _request_id.reset(token)
