"""Concurrency-safe AI subscription reservation, settlement and usage ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.ai_usage import (
    AIUsageCounter,
    AIUsageEvent,
    AIUsagePolicy,
    AIUsageReservation,
)


class AIUsageQuotaExceeded(PermissionError):
    """Raised when no valid subscription policy or remaining quota is available."""


@dataclass(frozen=True, slots=True)
class AIUsageReservationHandle:
    reservation_id: UUID
    max_output_tokens: int


class AIUsageMeter:
    def __init__(self, *, db: Session, settings) -> None:
        self.db = db
        self.settings = settings
        self._pricing = json.loads(settings.ai_model_pricing_json)
        self.reservation_ttl_seconds = settings.ai_usage_reservation_ttl_seconds

    def _set_rls_context(self, hospital_id: UUID, actor_user_id: UUID) -> None:
        self.db.execute(
            text("SELECT set_config('app.current_hospital_id', :value, true)"),
            {"value": str(hospital_id)},
        )
        self.db.execute(
            text("SELECT set_config('app.current_user_id', :value, true)"),
            {"value": str(actor_user_id)},
        )

    @staticmethod
    def _cost(tokens_in: int, tokens_out: int, pricing: dict | None) -> int | None:
        if pricing is None:
            return None
        numerator = (
            tokens_in * pricing["input_micros_per_million_tokens"]
            + tokens_out * pricing["output_micros_per_million_tokens"]
        )
        return (numerator + 999_999) // 1_000_000

    def reserve(
        self,
        *,
        hospital_id: UUID,
        actor_user_id: UUID,
        capability: str,
        operating_mode: str,
        provider_class: str,
        provider_id: str,
        model_id: str,
        model_version: str,
        estimated_input_tokens: int,
        provider_max_output_tokens: int,
        now: datetime | None = None,
    ) -> AIUsageReservationHandle:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise AIUsageQuotaExceeded("usage_reservation_requires_timezone")
        if estimated_input_tokens < 1 or provider_max_output_tokens < 1:
            raise AIUsageQuotaExceeded("invalid_usage_reservation_size")

        today: date = current.date()
        policies = self.db.scalars(
            select(AIUsagePolicy)
            .where(
                AIUsagePolicy.hospital_id == hospital_id,
                AIUsagePolicy.status == "active",
                AIUsagePolicy.period_start <= today,
                AIUsagePolicy.period_end > today,
            )
            .order_by(AIUsagePolicy.period_start.desc())
            .limit(2)
            .with_for_update()
        ).all()
        if not policies:
            raise AIUsageQuotaExceeded("ai_usage_policy_not_configured")
        if len(policies) != 1:
            raise AIUsageQuotaExceeded("ambiguous_ai_usage_policy")
        policy = policies[0]

        insert_counter = pg_insert(AIUsageCounter).values(
            hospital_id=hospital_id,
            policy_id=policy.id,
            requests_used=0,
            requests_reserved=0,
            input_tokens_used=0,
            input_tokens_reserved=0,
            output_tokens_used=0,
            output_tokens_reserved=0,
            cost_micros_used=0,
            cost_micros_reserved=0,
        ).on_conflict_do_nothing(index_elements=["hospital_id", "policy_id"])
        self.db.execute(insert_counter)
        counter = self.db.scalar(
            select(AIUsageCounter)
            .where(
                AIUsageCounter.hospital_id == hospital_id,
                AIUsageCounter.policy_id == policy.id,
            )
            .with_for_update()
        )
        if counter is None:
            raise AIUsageQuotaExceeded("ai_usage_counter_unavailable")

        pricing = self._pricing.get(f"{provider_id}:{model_id}")
        if pricing is not None and pricing.get("currency") != policy.currency:
            raise AIUsageQuotaExceeded("ai_model_pricing_currency_mismatch")
        if policy.cost_limit_micros is not None and pricing is None:
            raise AIUsageQuotaExceeded("model_pricing_required_for_cost_limited_plan")

        max_output_tokens = min(
            provider_max_output_tokens, policy.max_output_tokens_per_request
        )
        estimated_cost = self._cost(
            estimated_input_tokens, max_output_tokens, pricing
        ) or 0

        if counter.requests_used + counter.requests_reserved + 1 > policy.request_limit:
            raise AIUsageQuotaExceeded("monthly_ai_request_limit_reached")
        if (
            counter.input_tokens_used + counter.input_tokens_reserved + estimated_input_tokens
            > policy.input_token_limit
        ):
            raise AIUsageQuotaExceeded("monthly_ai_input_token_limit_reached")
        if (
            counter.output_tokens_used + counter.output_tokens_reserved + max_output_tokens
            > policy.output_token_limit
        ):
            raise AIUsageQuotaExceeded("monthly_ai_output_token_limit_reached")
        if (
            policy.cost_limit_micros is not None
            and counter.cost_micros_used + counter.cost_micros_reserved + estimated_cost
            > policy.cost_limit_micros
        ):
            raise AIUsageQuotaExceeded("monthly_ai_cost_limit_reached")

        reservation_id = uuid4()
        reservation = AIUsageReservation(
            id=reservation_id,
            hospital_id=hospital_id,
            policy_id=policy.id,
            counter_id=counter.id,
            actor_user_id=actor_user_id,
            idempotency_key=uuid4(),
            capability=capability,
            operating_mode=operating_mode,
            provider_class=provider_class,
            provider_id=provider_id,
            model_id=model_id,
            model_version=model_version,
            reserved_input_tokens=estimated_input_tokens,
            reserved_output_tokens=max_output_tokens,
            estimated_cost_micros=estimated_cost,
            currency=policy.currency,
            pricing_snapshot_json=pricing,
            status="reserved",
            expires_at=current + timedelta(seconds=self.reservation_ttl_seconds),
        )
        counter.requests_reserved += 1
        counter.input_tokens_reserved += estimated_input_tokens
        counter.output_tokens_reserved += max_output_tokens
        counter.cost_micros_reserved += estimated_cost
        self.db.add(reservation)
        self.db.commit()
        self._set_rls_context(hospital_id, actor_user_id)
        return AIUsageReservationHandle(
            reservation_id=reservation_id,
            max_output_tokens=max_output_tokens,
        )

    def settle(
        self,
        handle: AIUsageReservationHandle,
        *,
        hospital_id: UUID,
        actor_user_id: UUID,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        usage_is_estimated: bool,
        outcome: str = "success",
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or input_tokens < 0 or output_tokens < 0 or latency_ms < 0:
            raise AIUsageQuotaExceeded("invalid_usage_settlement")
        if outcome not in {"success", "withheld"}:
            raise AIUsageQuotaExceeded("invalid_usage_outcome")
        self._set_rls_context(hospital_id, actor_user_id)
        reservation = self.db.scalar(
            select(AIUsageReservation)
            .where(
                AIUsageReservation.id == handle.reservation_id,
                AIUsageReservation.hospital_id == hospital_id,
                AIUsageReservation.actor_user_id == actor_user_id,
            )
            .with_for_update()
        )
        if reservation is None or reservation.status != "reserved":
            raise AIUsageQuotaExceeded("usage_reservation_not_active")
        counter = self.db.scalar(
            select(AIUsageCounter)
            .where(
                AIUsageCounter.id == reservation.counter_id,
                AIUsageCounter.hospital_id == hospital_id,
            )
            .with_for_update()
        )
        if counter is None:
            raise AIUsageQuotaExceeded("ai_usage_counter_unavailable")

        actual_cost = self._cost(
            input_tokens, output_tokens, reservation.pricing_snapshot_json
        )
        counter.requests_reserved = max(0, counter.requests_reserved - 1)
        counter.input_tokens_reserved = max(
            0, counter.input_tokens_reserved - reservation.reserved_input_tokens
        )
        counter.output_tokens_reserved = max(
            0, counter.output_tokens_reserved - reservation.reserved_output_tokens
        )
        counter.cost_micros_reserved = max(
            0, counter.cost_micros_reserved - reservation.estimated_cost_micros
        )
        counter.requests_used += 1
        counter.input_tokens_used += input_tokens
        counter.output_tokens_used += output_tokens
        if actual_cost is not None:
            counter.cost_micros_used += actual_cost

        reservation.status = "settled"
        reservation.settled_at = current
        self.db.add(AIUsageEvent(
            hospital_id=hospital_id,
            reservation_id=reservation.id,
            actor_user_id=actor_user_id,
            capability=reservation.capability,
            operating_mode=reservation.operating_mode,
            provider_id=reservation.provider_id,
            model_id=reservation.model_id,
            model_version=reservation.model_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=actual_cost,
            currency=reservation.currency,
            latency_ms=latency_ms,
            usage_is_estimated=usage_is_estimated,
            outcome=outcome,
        ))
        self.db.commit()
        self._set_rls_context(hospital_id, actor_user_id)

    def release_failed(
        self,
        handle: AIUsageReservationHandle,
        *,
        hospital_id: UUID,
        actor_user_id: UUID,
        latency_ms: int,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or latency_ms < 0:
            raise AIUsageQuotaExceeded("invalid_usage_release")
        self._set_rls_context(hospital_id, actor_user_id)
        reservation = self.db.scalar(
            select(AIUsageReservation)
            .where(
                AIUsageReservation.id == handle.reservation_id,
                AIUsageReservation.hospital_id == hospital_id,
                AIUsageReservation.actor_user_id == actor_user_id,
            )
            .with_for_update()
        )
        if reservation is None or reservation.status != "reserved":
            raise AIUsageQuotaExceeded("usage_reservation_not_active")
        counter = self.db.scalar(
            select(AIUsageCounter)
            .where(
                AIUsageCounter.id == reservation.counter_id,
                AIUsageCounter.hospital_id == hospital_id,
            )
            .with_for_update()
        )
        if counter is None:
            raise AIUsageQuotaExceeded("ai_usage_counter_unavailable")

        counter.requests_reserved = max(0, counter.requests_reserved - 1)
        counter.input_tokens_reserved = max(
            0, counter.input_tokens_reserved - reservation.reserved_input_tokens
        )
        counter.output_tokens_reserved = max(
            0, counter.output_tokens_reserved - reservation.reserved_output_tokens
        )
        counter.cost_micros_reserved = max(
            0, counter.cost_micros_reserved - reservation.estimated_cost_micros
        )
        counter.requests_used += 1
        counter.input_tokens_used += reservation.reserved_input_tokens
        if reservation.pricing_snapshot_json is not None:
            counter.cost_micros_used += reservation.estimated_cost_micros

        reservation.status = "released"
        reservation.settled_at = current
        self.db.add(AIUsageEvent(
            hospital_id=hospital_id,
            reservation_id=reservation.id,
            actor_user_id=actor_user_id,
            capability=reservation.capability,
            operating_mode=reservation.operating_mode,
            provider_id=reservation.provider_id,
            model_id=reservation.model_id,
            model_version=reservation.model_version,
            input_tokens=reservation.reserved_input_tokens,
            output_tokens=0,
            cost_micros=(
                reservation.estimated_cost_micros
                if reservation.pricing_snapshot_json is not None else None
            ),
            currency=reservation.currency,
            latency_ms=latency_ms,
            usage_is_estimated=True,
            outcome="failed",
        ))
        self.db.commit()
        self._set_rls_context(hospital_id, actor_user_id)

    def current_snapshot(
        self, *, hospital_id: UUID, now: datetime | None = None
    ) -> dict:
        current = now or datetime.now(timezone.utc)
        today = current.date()
        policies = self.db.scalars(
            select(AIUsagePolicy)
            .where(
                AIUsagePolicy.hospital_id == hospital_id,
                AIUsagePolicy.status == "active",
                AIUsagePolicy.period_start <= today,
                AIUsagePolicy.period_end > today,
            )
            .order_by(AIUsagePolicy.period_start.desc())
            .limit(2)
        ).all()
        if not policies:
            return {"configured": False}
        if len(policies) != 1:
            raise AIUsageQuotaExceeded("ambiguous_ai_usage_policy")
        policy = policies[0]
        counter = self.db.scalar(
            select(AIUsageCounter).where(
                AIUsageCounter.hospital_id == hospital_id,
                AIUsageCounter.policy_id == policy.id,
            )
        )
        values = {
            "requests_used": counter.requests_used if counter else 0,
            "requests_reserved": counter.requests_reserved if counter else 0,
            "input_tokens_used": counter.input_tokens_used if counter else 0,
            "input_tokens_reserved": counter.input_tokens_reserved if counter else 0,
            "output_tokens_used": counter.output_tokens_used if counter else 0,
            "output_tokens_reserved": counter.output_tokens_reserved if counter else 0,
            "cost_micros_used": counter.cost_micros_used if counter else 0,
            "cost_micros_reserved": counter.cost_micros_reserved if counter else 0,
        }
        return {
            "configured": True,
            "plan_code": policy.plan_code,
            "subscription_reference": policy.subscription_reference,
            "period_start": policy.period_start,
            "period_end": policy.period_end,
            "request_limit": policy.request_limit,
            "input_token_limit": policy.input_token_limit,
            "output_token_limit": policy.output_token_limit,
            "max_output_tokens_per_request": policy.max_output_tokens_per_request,
            "cost_limit_micros": policy.cost_limit_micros,
            "currency": policy.currency,
            **values,
        }

    def release_expired_reservations(
        self,
        *,
        hospital_id: UUID,
        actor_user_id: UUID,
        now: datetime | None = None,
        batch_size: int = 100,
    ) -> int:
        """Release stale reservations for one authenticated hospital/user context."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or not 1 <= batch_size <= 1000:
            raise AIUsageQuotaExceeded("invalid_expired_reservation_cleanup")
        self._set_rls_context(hospital_id, actor_user_id)
        reservations = self.db.scalars(
            select(AIUsageReservation)
            .where(
                AIUsageReservation.hospital_id == hospital_id,
                AIUsageReservation.actor_user_id == actor_user_id,
                AIUsageReservation.status == "reserved",
                AIUsageReservation.expires_at <= current,
            )
            .order_by(AIUsageReservation.expires_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        for reservation in reservations:
            counter = self.db.scalar(
                select(AIUsageCounter)
                .where(
                    AIUsageCounter.id == reservation.counter_id,
                    AIUsageCounter.hospital_id == hospital_id,
                )
                .with_for_update()
            )
            if counter is None:
                raise AIUsageQuotaExceeded("ai_usage_counter_unavailable")
            counter.requests_reserved = max(0, counter.requests_reserved - 1)
            counter.input_tokens_reserved = max(
                0, counter.input_tokens_reserved - reservation.reserved_input_tokens
            )
            counter.output_tokens_reserved = max(
                0, counter.output_tokens_reserved - reservation.reserved_output_tokens
            )
            counter.cost_micros_reserved = max(
                0, counter.cost_micros_reserved - reservation.estimated_cost_micros
            )
            counter.requests_used += 1
            counter.input_tokens_used += reservation.reserved_input_tokens
            if reservation.pricing_snapshot_json is not None:
                counter.cost_micros_used += reservation.estimated_cost_micros
            reservation.status = "released"
            reservation.settled_at = current
            self.db.add(AIUsageEvent(
                hospital_id=hospital_id,
                reservation_id=reservation.id,
                actor_user_id=actor_user_id,
                capability=reservation.capability,
                operating_mode=reservation.operating_mode,
                provider_id=reservation.provider_id,
                model_id=reservation.model_id,
                model_version=reservation.model_version,
                input_tokens=reservation.reserved_input_tokens,
                output_tokens=0,
                cost_micros=(
                    reservation.estimated_cost_micros
                    if reservation.pricing_snapshot_json is not None else None
                ),
                currency=reservation.currency,
                latency_ms=0,
                usage_is_estimated=True,
                outcome="failed",
            ))
        self.db.commit()
        self._set_rls_context(hospital_id, actor_user_id)
        return len(reservations)
