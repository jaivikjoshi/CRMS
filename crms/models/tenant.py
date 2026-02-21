"""Tenant model."""

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crms.database import Base


class Tenant(Base):
    """Tenant table - one per API key."""

    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(
        "created_at", type_=String(50)
    )  # timestamptz as string for simplicity
