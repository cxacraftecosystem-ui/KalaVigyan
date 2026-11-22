import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.mcp_cors import OpenCorsMiddleware
from app.api.router import api_router
from app.api.routes.auth import (
    ACCESS_STATUS_HEADER,
    SESSION_TOKEN_HEADER,
    SIGN_IN_HINT_HEADER,
    TWO_FACTOR_REQUIRED_HEADER,
)
from app.api.routes.oauth_well_known import router as oauth_well_known_router
from app.api.routes.password_change import CONFIRM_PROVIDER_HEADER
from app.api.voice_deps import voice_stored_search
from app.core.config import get_settings
from app.core.db import dispose_engine, ping
from app.core.deps import PASSWORD_CHANGE_REQUIRED_HEADER, TWO_FACTOR_SETUP_REQUIRED_HEADER
from app.core.logging import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    configure_logging,
    current_request_id,
)
from app.core.security import verify_jwt_configuration
from app.core.shielded import ShieldedWork
from app.services import two_factor
from app.services.craft_catalogue import new_catalogue_cache
from app.services.craft_page_cache import PageCache
from app.services.craft_resolver import CraftIndexStore
from app.services.live_sources import LiveSourcesStore
from app.services.public_summary import SummaryCache
from app.services.river_topology import TopologyCache
from app.voice.runtime import VoiceRuntime
from app.voice.sessions import VOICE_CONSENT_HEADER

logger = logging.getLogger("kalavigyan")

READINESS_TIMEOUT_SECONDS = 3.0
API_VERSION = "0.0.1"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        private = str(scope.get("path") or "").startswith("/api")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {name.lower() for name, _ in headers}
                additions = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                ]
                if private:
                    additions.append((b"cache-control", b"no-store"))
                if self.hsts:
                    additions.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
                headers.extend((name, value) for name, value in additions if name not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.shielded_work.drain()
    await app.state.live_sources.aclose()
    await app.state.voice_runtime.aclose()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    verify_jwt_configuration()
    two_factor.verify_key_configuration()
    app = FastAPI(
        title="KalaVigyan API",
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.backend_expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.backend_expose_docs else None,
    )
    app.state.craft_index = CraftIndexStore()
    app.state.live_sources = LiveSourcesStore()
    app.state.shielded_work = ShieldedWork()
    app.state.voice_runtime = VoiceRuntime(search=voice_stored_search)
    app.state.river_topologies = TopologyCache()
    app.state.public_summary = SummaryCache()
    app.state.craft_catalogue = new_catalogue_cache()
    app.state.craft_pages = PageCache()

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Something went wrong. Try again.", "requestId": current_request_id()},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Two-Factor-Code",
            "Idempotency-Key",
            "If-None-Match",
        ],
        expose_headers=[
            ACCESS_STATUS_HEADER,
            CONFIRM_PROVIDER_HEADER,
            SIGN_IN_HINT_HEADER,
            SESSION_TOKEN_HEADER,
            TWO_FACTOR_REQUIRED_HEADER,
            TWO_FACTOR_SETUP_REQUIRED_HEADER,
            PASSWORD_CHANGE_REQUIRED_HEADER,
            REQUEST_ID_HEADER,
            "Retry-After",
            "ETag",
            VOICE_CONSENT_HEADER,
        ],
        max_age=600,
    )
    app.add_middleware(OpenCorsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "release": settings.release, "version": API_VERSION}

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> JSONResponse:
        started = time.perf_counter()
        reachable = True
        try:
            async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
                await ping()
        except Exception as exc:
            reachable = False
            logger.warning("readiness probe failed", extra={"error": type(exc).__name__})
        return JSONResponse(
            status_code=status.HTTP_200_OK if reachable else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "ready" if reachable else "unavailable",
                "database": reachable,
                "latencyMs": round((time.perf_counter() - started) * 1000, 1),
            },
            headers={"cache-control": "no-store"},
        )

    app.include_router(api_router)
    app.include_router(oauth_well_known_router)
    return app


app = create_app()
