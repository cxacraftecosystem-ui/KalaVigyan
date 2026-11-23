import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import build_runtime_database_url
from app.core.downgrade_guard import planned_downgrade, refuse_long_downgrade
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

EXCLUDED_TABLES = frozenset({"spatial_ref_sys"})


def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in EXCLUDED_TABLES)


def run_migrations_offline() -> None:
    runtime = build_runtime_database_url(get_settings().database_url)
    context.configure(
        url=runtime.url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        transaction_per_migration=True,
    )
    settings = get_settings()
    refuse_long_downgrade(
        planned_downgrade(context.get_context()),
        production=settings.is_production,
        confirmed_steps=settings.confirm_downgrade_steps,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    runtime = build_runtime_database_url(get_settings().database_url)
    engine = create_async_engine(runtime.url, connect_args=runtime.connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
