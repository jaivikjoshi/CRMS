"""API key authentication middleware."""

import hashlib
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from crms.config import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crms.database import get_db
from crms.models.tenant import Tenant


API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Hash API key with salt for storage/lookup."""
    return hashlib.sha256(
        f"{settings.api_key_hash_salt}:{api_key}".encode()
    ).hexdigest()


async def get_tenant_from_bearer(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_header: str | None = Depends(API_KEY_HEADER),
) -> Tenant:
    """Extract tenant from Bearer token (API key)."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    api_key = auth_header[7:].strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    api_key_hash = hash_api_key(api_key)
    result = await db.execute(
        select(Tenant).where(Tenant.api_key_hash == api_key_hash)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return tenant


# Type alias for dependency injection
TenantDep = Annotated[Tenant, Depends(get_tenant_from_bearer)]
