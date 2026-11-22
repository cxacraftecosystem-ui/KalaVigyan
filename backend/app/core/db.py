import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings, is_local_db_host
from app.core.research_gate import ResearchGate, gated_session_class, research_slots

logger = logging.getLogger(__name__)

SESSION_POOLER_PORT = 5432
TRANSACTION_POOLER_PORT = 6543

_PRISMA_ONLY_PARAMS = frozenset(
    {"pgbouncer", "connection_limit", "pool_timeout", "schema", "socket_timeout", "statement_cache_size"}
)


@dataclass(frozen=True)
class RuntimeDatabase:
    url: str
    connect_args: dict[str, Any] = field(default_factory=dict)
    transaction_pooler: bool = False


def build_runtime_database_url(base_url: str) -> RuntimeDatabase:
    settings = get_settings()
    try:
        parts = urlsplit(base_url)
    except ValueError as exc:
        raise ValueError("DATABASE_URL is not a valid URL") from exc
    scheme = parts.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+psycopg"
    elif not scheme.startswith("postgresql+"):
        raise ValueError("DATABASE_URL must be a postgres:// or postgresql:// URL")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _PRISMA_ONLY_PARAMS
    ]
    present = {k.lower() for k, _ in query}
    host = parts.hostname or ""
    transaction_pooler = parts.port == TRANSACTION_POOLER_PORT or any(
        k.lower() == "pgbouncer" for k, _ in parse_qsl(parts.query)
    )
    connect_args: dict[str, Any] = {"connect_timeout": settings.database_connect_timeout}
    if transaction_pooler:
        connect_args["prepare_threshold"] = None
    if not is_local_db_host(host) and "application_name" not in present:
        query.append(("application_name", "kalavigyan-api"))
    url = urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return RuntimeDatabase(url=url, connect_args=connect_args, transaction_pooler=transaction_pooler)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_research_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        runtime = build_runtime_database_url(settings.database_url)
        if runtime.transaction_pooler:
            logger.warning("DATABASE_URL points at the transaction pooler; prepared statements are disabled")
        _engine = create_async_engine(
            runtime.url,
            connect_args=runtime.connect_args,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        yield session


async def release_connection(session: AsyncSession) -> None:
    await session.commit()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def ping() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    global _engine, _sessionmaker, _research_sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
    _research_sessionmaker = None


def research_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _research_sessionmaker
    if _research_sessionmaker is None:
        settings = get_settings()
        gate = ResearchGate(research_slots(settings.database_pool_size, settings.database_max_overflow))
        _research_sessionmaker = async_sessionmaker(
            get_engine(), class_=gated_session_class(gate), expire_on_commit=False, autoflush=False
        )
    return _research_sessionmaker
