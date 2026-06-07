from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models.execution_reconciliation_job import ExecutionReconciliationJob
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_reconciliation_jobs import ExecutionReconciliationJobService
from tests.test_execution_reconciliation_api import add_attempt


NOW = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


def test_reconciliation_job_model_schema(db_session) -> None:
    inspector = inspect(db_session.bind)

    assert "execution_reconciliation_jobs" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("execution_reconciliation_jobs")}
    assert {
        "id",
        "execution_attempt_id",
        "bot_id",
        "state",
        "next_attempt_at",
        "lease_token",
        "lease_expires_at",
        "automatic_attempt_count",
        "last_checked_at",
        "last_resolution",
        "last_failure_category",
        "resolved_at",
        "created_at",
        "updated_at",
    }.issubset(columns)
    indexes = {index["name"] for index in inspector.get_indexes("execution_reconciliation_jobs")}
    assert "ix_execution_reconciliation_jobs_state_next_attempt_at" in indexes
    assert "ix_execution_reconciliation_jobs_state_lease_expires_at" in indexes


def test_reconciliation_job_attempt_unique_and_count_non_negative(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(db_session, bot_id=bot.id)
    job_repository = ExecutionReconciliationJobRepository(db_session)
    job_repository.create_pending(execution_attempt_id=attempt.id, bot_id=bot.id, next_attempt_at=NOW)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(
            ExecutionReconciliationJob(
                execution_attempt_id=attempt.id,
                bot_id=bot.id,
                state="pending",
                next_attempt_at=NOW,
            )
        )
        db_session.commit()
    db_session.rollback()

    job = job_repository.get_by_execution_attempt_id(attempt.id)
    job.automatic_attempt_count = -1
    db_session.add(job)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_enqueue_creates_one_pending_job_only_for_eligible_attempts(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    service = job_service(db_session)
    eligible = add_attempt(db_session, bot_id=bot.id)

    first = service.ensure_pending_job_for_attempt(execution_attempt_id=eligible.id, next_attempt_at=NOW)
    second = service.ensure_pending_job_for_attempt(execution_attempt_id=eligible.id, next_attempt_at=NOW + timedelta(hours=1))

    assert first.enqueued is True
    assert first.reason == "created"
    assert second.reason == "already_exists"
    assert job_repository(db_session).get_by_execution_attempt_id(eligible.id).next_attempt_at == NOW

    recovered = add_attempt(
        db_session,
        bot_id=bot.id,
        final_status="order_created",
        final_reason="testnet_order_recovered_after_unknown_submission",
        metadata={
            "client_order_id": "tap_recovered",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "found",
            "submission_recovered": True,
        },
    )
    ineligible = [
        add_attempt(db_session, bot_id=bot.id, mode="paper", broker="paper"),
        add_attempt(db_session, bot_id=bot.id, mode="live", broker="live"),
        add_attempt(db_session, bot_id=bot.id, final_reason="binance_testnet_order_rejected", metadata={}),
        add_attempt(db_session, bot_id=bot.id, final_reason="testnet_quantity_below_minimum", metadata={}),
        add_attempt(db_session, bot_id=bot.id, final_reason="testnet_insufficient_balance", metadata={}),
        add_attempt(db_session, bot_id=bot.id, final_reason="testnet_order_submission_dry_run", metadata={}),
        add_attempt(db_session, bot_id=bot.id, symbol=""),
        add_attempt(
            db_session,
            bot_id=bot.id,
            metadata={
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_resolution": "unresolved",
                "submission_recovered": False,
            },
        ),
    ]

    assert service.ensure_pending_job_for_attempt(execution_attempt_id=recovered.id, next_attempt_at=NOW).reason == "already_recovered"
    for attempt in ineligible:
        result = service.ensure_pending_job_for_attempt(execution_attempt_id=attempt.id, next_attempt_at=NOW)
        assert result.enqueued is False
        assert job_repository(db_session).get_by_execution_attempt_id(attempt.id) is None


def test_enqueue_does_not_reset_resolved_or_active_claimed_job(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    service = job_service(db_session, now=NOW)
    attempt = add_attempt(db_session, bot_id=bot.id)
    job = service.ensure_pending_job_for_attempt(execution_attempt_id=attempt.id, next_attempt_at=NOW).job
    claimed = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=1)[0]

    active = service.ensure_pending_job_for_attempt(execution_attempt_id=attempt.id, next_attempt_at=NOW + timedelta(hours=1))

    assert active.reason == "active_claim_exists"
    assert job_repository(db_session).get_by_id(job.id).state == "claimed"

    job_repository(db_session).mark_claimed_job_resolved(
        job_id=job.id,
        lease_token=claimed.lease_token,
        checked_at=NOW,
        resolution="found",
    )
    db_session.commit()
    resolved = service.ensure_pending_job_for_attempt(execution_attempt_id=attempt.id, next_attempt_at=NOW + timedelta(hours=2))

    assert resolved.reason == "already_resolved"
    assert job_repository(db_session).get_by_id(job.id).state == "resolved"


def test_recording_immediate_unresolved_attempt_enqueues_but_recovered_does_not(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    settings = settings_with_delay(monkeypatch, delay=120)
    created_at_before = NOW

    unresolved = ExecutionAttemptService(ExecutionAttemptRepository(db_session)).record(
        bot_id=bot.id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=1,
        requested_price=None,
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status="rejected_by_broker",
        final_reason="testnet_order_reconciliation_unresolved",
        metadata={
            "client_order_id": "tap_unresolved",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
        },
    )
    recovered = ExecutionAttemptService(ExecutionAttemptRepository(db_session)).record(
        bot_id=bot.id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=1,
        requested_price=None,
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status="order_created",
        final_reason="testnet_order_recovered_after_unknown_submission",
        metadata={
            "client_order_id": "tap_recovered",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "found",
            "submission_recovered": True,
        },
    )

    assert settings.binance_testnet_reconciliation_initial_delay_seconds == 120
    assert job_repository(db_session).get_by_execution_attempt_id(unresolved.id) is not None
    assert job_repository(db_session).get_by_execution_attempt_id(recovered.id) is None


def test_claim_release_resolve_and_exhaust_lifecycle(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    due_early = add_job(db_session, bot.id, NOW - timedelta(minutes=10))
    due_late = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    future = add_job(db_session, bot.id, NOW + timedelta(minutes=10))

    claimed = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=30, limit=1)
    assert [item.id for item in claimed] == [due_early.id]
    assert claimed[0].lease_token
    assert claimed[0].lease_expires_at == NOW + timedelta(seconds=30)
    assert job_repository(db_session).get_by_id(future.id).state == "pending"

    second = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=30, limit=10)
    assert [item.id for item in second] == [due_late.id]
    exhausted = job_repository(db_session).mark_claimed_job_exhausted(
        job_id=due_late.id,
        lease_token=second[0].lease_token,
        checked_at=NOW,
        resolution="failed",
        failure_category="timeout",
    )
    assert exhausted.state == "exhausted"
    assert exhausted.automatic_attempt_count == 1

    assert job_repository(db_session).release_claimed_job_for_retry(
        job_id=due_early.id,
        lease_token="stale",
        next_attempt_at=NOW,
        checked_at=NOW,
        resolution="not_found",
        failure_category="http_error",
    ) is None
    released = job_repository(db_session).release_claimed_job_for_retry(
        job_id=due_early.id,
        lease_token=claimed[0].lease_token,
        next_attempt_at=NOW + timedelta(minutes=5),
        checked_at=NOW,
        resolution="not_found",
        failure_category="http_error",
    )
    assert released.state == "pending"
    assert released.automatic_attempt_count == 1
    assert released.lease_token is None

    expired_claim = job_repository(db_session).claim_due_jobs(now=NOW + timedelta(minutes=6), lease_seconds=30, limit=1)[0]
    assert expired_claim.id == due_early.id
    assert expired_claim.lease_token != claimed[0].lease_token
    assert job_repository(db_session).mark_claimed_job_resolved(
        job_id=due_early.id,
        lease_token=claimed[0].lease_token,
        checked_at=NOW,
        resolution="found",
    ) is None
    resolved = job_repository(db_session).mark_claimed_job_resolved(
        job_id=due_early.id,
        lease_token=expired_claim.lease_token,
        checked_at=NOW + timedelta(minutes=6),
        resolution="found",
    )
    assert resolved.state == "resolved"
    assert resolved.automatic_attempt_count == 2
    assert resolved.lease_token is None
    assert job_repository(db_session).get_by_id(due_late.id).lease_token is None


def test_claim_limit_validation_and_no_binance_calls(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    add_job(db_session, bot.id, NOW)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Lifecycle methods must not call Binance")

    from app.services.brokers.binance import BinanceTestnetOrderClient

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_called)
    with pytest.raises(ValueError):
        job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=0)
    with pytest.raises(ValueError):
        job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=0, limit=1)


def test_reconciliation_status_exposes_safe_delayed_lifecycle_fields(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    pending = add_job(db_session, bot.id, NOW + timedelta(minutes=10))
    claimed = add_job(db_session, bot.id, NOW - timedelta(minutes=5))
    expired = add_job(db_session, bot.id, NOW - timedelta(minutes=4))
    exhausted = add_job(db_session, bot.id, NOW - timedelta(minutes=3))
    claimed_token = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=1)[0].lease_token
    expired_token = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=1, limit=1)[0].lease_token
    exhausted_claim = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=1)[0]
    expired_job = job_repository(db_session).get_by_id(expired.id)
    expired_job.lease_expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.add(expired_job)
    db_session.commit()
    job_repository(db_session).mark_claimed_job_exhausted(
        job_id=exhausted.id,
        lease_token=exhausted_claim.lease_token,
        checked_at=NOW,
        resolution="failed",
        failure_category="timeout",
    )
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["pending_delayed_reconciliation_count"] == 1
    assert body["claimed_delayed_reconciliation_count"] == 2
    assert body["expired_lease_count"] == 1
    assert body["exhausted_delayed_reconciliation_count"] == 1
    attempts = body["recent_attempts"]
    pending_attempt = next(item for item in attempts if item["attempt_id"] == pending.execution_attempt_id)
    assert pending_attempt["delayed_reconciliation_job_id"] == pending.id
    assert pending_attempt["delayed_reconciliation_state"] == "pending"
    assert pending_attempt["delayed_reconciliation_next_attempt_at"] is not None
    assert pending_attempt["delayed_reconciliation_automatic_attempt_count"] == 0
    assert "lease_token" not in response.text
    assert claimed_token not in response.text
    assert expired_token not in response.text
    assert "metadata" not in response.text


def job_repository(db_session) -> ExecutionReconciliationJobRepository:
    return ExecutionReconciliationJobRepository(db_session)


def job_service(db_session, *, now=NOW) -> ExecutionReconciliationJobService:
    return ExecutionReconciliationJobService(
        ExecutionAttemptRepository(db_session),
        job_repository(db_session),
        now_provider=lambda: now,
    )


def add_job(db_session, bot_id: int, next_attempt_at: datetime) -> ExecutionReconciliationJob:
    attempt = add_attempt(db_session, bot_id=bot_id)
    job = job_service(db_session).ensure_pending_job_for_attempt(
        execution_attempt_id=attempt.id,
        next_attempt_at=next_attempt_at,
    ).job
    db_session.commit()
    return job


def settings_with_delay(monkeypatch, *, delay: int):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "binance_testnet_reconciliation_initial_delay_seconds", delay)
    return settings
