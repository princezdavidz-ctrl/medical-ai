import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class AIUsagePolicy(TimestampMixin, Base):
    """Hospital subscription limits for one billing period."""

    __tablename__ = "ai_usage_policies"
    __table_args__ = (
        UniqueConstraint("hospital_id", "period_start", "period_end", name="uq_ai_usage_policy_period"),
        CheckConstraint("period_end > period_start", name="ck_ai_usage_policy_period"),
        CheckConstraint("request_limit > 0", name="ck_ai_usage_policy_request_limit"),
        CheckConstraint("input_token_limit > 0", name="ck_ai_usage_policy_input_limit"),
        CheckConstraint("output_token_limit > 0", name="ck_ai_usage_policy_output_limit"),
        CheckConstraint("max_output_tokens_per_request > 0", name="ck_ai_usage_policy_max_output"),
        CheckConstraint("cost_limit_micros IS NULL OR cost_limit_micros >= 0", name="ck_ai_usage_policy_cost_limit"),
        CheckConstraint("status IN ('active', 'suspended', 'expired')", name="ck_ai_usage_policy_status"),
        Index("ix_ai_usage_policy_hospital_status", "hospital_id", "status", "period_start", "period_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    subscription_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(80), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    request_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_token_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_token_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_output_tokens_per_request: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_limit_micros: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class AIUsageCounter(TimestampMixin, Base):
    """Atomic monthly usage and reservation counters for one hospital policy."""

    __tablename__ = "ai_usage_counters"
    __table_args__ = (
        UniqueConstraint("hospital_id", "policy_id", name="uq_ai_usage_counter_policy"),
        CheckConstraint("requests_used >= 0 AND requests_reserved >= 0", name="ck_ai_usage_counter_requests"),
        CheckConstraint("input_tokens_used >= 0 AND input_tokens_reserved >= 0", name="ck_ai_usage_counter_input"),
        CheckConstraint("output_tokens_used >= 0 AND output_tokens_reserved >= 0", name="ck_ai_usage_counter_output"),
        CheckConstraint("cost_micros_used >= 0 AND cost_micros_reserved >= 0", name="ck_ai_usage_counter_cost"),
        Index("ix_ai_usage_counter_hospital", "hospital_id", "policy_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_usage_policies.id"), nullable=False)
    requests_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    requests_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    input_tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    input_tokens_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_micros_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_micros_reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class AIUsageReservation(Base):
    """Preflight reservation that prevents concurrent requests exceeding subscription limits."""

    __tablename__ = "ai_usage_reservations"
    __table_args__ = (
        UniqueConstraint("hospital_id", "idempotency_key", name="uq_ai_usage_reservation_idempotency"),
        CheckConstraint("status IN ('reserved', 'settled', 'released')", name="ck_ai_usage_reservation_status"),
        CheckConstraint("reserved_input_tokens >= 0 AND reserved_output_tokens >= 0", name="ck_ai_usage_reservation_tokens"),
        CheckConstraint("estimated_cost_micros >= 0", name="ck_ai_usage_reservation_cost"),
        Index("ix_ai_usage_reservation_hospital_status", "hospital_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_usage_policies.id"), nullable=False)
    counter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_usage_counters.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    operating_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_class: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reserved_input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserved_output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pricing_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIUsageEvent(Base):
    """Append-only, privacy-minimal usage ledger; contains no prompts or patient identifiers."""

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_ai_usage_event_reservation"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="ck_ai_usage_event_tokens"),
        CheckConstraint("cost_micros IS NULL OR cost_micros >= 0", name="ck_ai_usage_event_cost"),
        CheckConstraint("latency_ms >= 0", name="ck_ai_usage_event_latency"),
        CheckConstraint("outcome IN ('success', 'withheld', 'failed')", name="ck_ai_usage_event_outcome"),
        Index("ix_ai_usage_event_hospital_created", "hospital_id", "created_at"),
        Index("ix_ai_usage_event_hospital_capability", "hospital_id", "capability", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_usage_reservations.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    operating_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    latency_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    usage_is_estimated: Mapped[bool] = mapped_column(nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
