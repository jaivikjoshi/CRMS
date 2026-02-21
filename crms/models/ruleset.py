"""Ruleset and Rule models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crms.database import Base


class Ruleset(Base):
    """Ruleset table - jurisdiction + tax_type per tenant."""

    __tablename__ = "rulesets"

    ruleset_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.tenant_id"), nullable=False
    )
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    tax_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        # Unique per tenant
        {"schema": None},
    )


class Rule(Base):
    """Draft rules - rule_pk, ruleset_id, rule_id, etc."""

    __tablename__ = "rules"

    rule_pk: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    ruleset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("rulesets.ruleset_id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft|published|deprecated
    updated_at: Mapped[str] = mapped_column(String(50), nullable=False)


class RulesetVersion(Base):
    """Published ruleset versions with effective windows."""

    __tablename__ = "ruleset_versions"

    version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    ruleset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("rulesets.ruleset_id"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)  # semver
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bundle_hash: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
