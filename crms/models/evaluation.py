"""Evaluation/audit model."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from crms.database import Base


class Evaluation(Base):
    """Evaluation audit records - append-only."""

    __tablename__ = "evaluations"

    evaluation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.tenant_id"), nullable=False
    )
    ruleset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("rulesets.ruleset_id"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ruleset_versions.version_id"), nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False)
