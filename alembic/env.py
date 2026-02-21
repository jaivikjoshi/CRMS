"""Alembic environment configuration."""

import asyncio
import ssl
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from crms.config import settings
from crms.database import Base
from crms.models import Evaluation, Rule, Ruleset, RulesetVersion, Tenant

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Strip sslmode from URL - asyncpg doesn't accept it; we use connect_args instead
_db_url = settings.database_url
if "sslmode=" in _db_url or "ssl=" in _db_url:
    parsed = urlparse(_db_url)
    query = parse_qs(parsed.query)
    query.pop("sslmode", None)
    query.pop("ssl", None)
    new_query = urlencode(query, doseq=True)
    _db_url = urlunparse(parsed._replace(query=new_query))

config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = config.get_main_option("sqlalchemy.url")
    # Supabase requires SSL - use permissive context to avoid macOS cert chain issues
    connect_args = {}
    if "supabase" in url or "pooler.supabase" in url:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
