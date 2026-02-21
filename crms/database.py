"""Database connection and session management."""

import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from crms.config import settings


def _make_ssl_context_for_supabase():
    """SSL context for Supabase - disables cert verification to avoid macOS chain issues."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_engine_url_and_connect_args():
    """Strip sslmode from URL (asyncpg doesn't accept it) and add SSL via connect_args for Supabase."""
    url = settings.database_url
    connect_args = {}
    if "sslmode=" in url or "ssl=" in url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query.pop("sslmode", None)
        query.pop("ssl", None)
        new_query = urlencode(query, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))
        if "supabase" in settings.database_url:
            connect_args["ssl"] = _make_ssl_context_for_supabase()
    return url, connect_args


_db_url, _connect_args = get_engine_url_and_connect_args()


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


engine = create_async_engine(
    _db_url,
    echo=settings.log_level == "DEBUG",
    connect_args=_connect_args,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
