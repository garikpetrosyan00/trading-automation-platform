from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.main import app
from app.models.execution_reconciliation_job import ExecutionReconciliationJob
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceOrderHttpResponse, BinanceTestnetOrderClient, BinanceTestnetOrderQueryClientError
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_reconciliation_jobs import ExecutionReconciliationJobService
from app.services.execution_reconciliation_worker import ExecutionReconciliationWorkerService
from tests.test_execution_reconciliation_api import add_attempt


NOW = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
RECONCILIATION_JOB_AUDIT_FIELDS = {
    "id",
    "execution_attempt_id",
    "bot_id",
    "status",
    "automatic_attempt_count",
    "max_automatic_attempts",
    "next_attempt_at",
    "claimed_at",
    "resolved_at",
    "exhausted_at",
    "last_result",
    "last_failure",
    "created_at",
    "updated_at",
}


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
    claimed_job = job_repository(db_session).get_by_id(claimed.id)
    claimed_job.lease_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    expired_job = job_repository(db_session).get_by_id(expired.id)
    expired_job.lease_expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.add(claimed_job)
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


def test_claim_due_jobs_respects_due_future_active_expired_batch_and_token_refresh(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    due_early = add_job(db_session, bot.id, NOW - timedelta(minutes=5))
    due_late = add_job(db_session, bot.id, NOW - timedelta(minutes=4))
    expired = add_job(db_session, bot.id, NOW - timedelta(minutes=3))
    active = add_job(db_session, bot.id, NOW - timedelta(minutes=2))
    future = add_job(db_session, bot.id, NOW + timedelta(minutes=10))
    expired.lease_token = "expired-token"
    expired.lease_expires_at = NOW - timedelta(seconds=1)
    expired.state = "claimed"
    active.lease_token = "active-token"
    active.lease_expires_at = NOW + timedelta(minutes=5)
    active.state = "claimed"
    db_session.add_all([expired, active])
    db_session.commit()

    first_batch = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=2)
    second_batch = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=10)

    assert [job.id for job in first_batch] == [due_early.id, due_late.id]
    assert [job.id for job in second_batch] == [expired.id]
    assert second_batch[0].lease_token != "expired-token"
    assert job_repository(db_session).get_by_id(active.id).lease_token == "active-token"
    assert job_repository(db_session).get_by_id(future.id).state == "pending"


def test_claim_due_jobs_does_not_reclaim_resolved_or_exhausted_jobs(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    resolved = add_job(db_session, bot.id, NOW - timedelta(minutes=3))
    exhausted = add_job(db_session, bot.id, NOW - timedelta(minutes=2))
    still_due = add_job(db_session, bot.id, NOW - timedelta(minutes=1))

    first_claims = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=3)
    first_claim_by_id = {claim.id: claim for claim in first_claims}
    assert set(first_claim_by_id) == {resolved.id, exhausted.id, still_due.id}

    job_repository(db_session).mark_claimed_job_resolved(
        job_id=resolved.id,
        lease_token=first_claim_by_id[resolved.id].lease_token,
        checked_at=NOW,
        resolution="found",
    )
    job_repository(db_session).mark_claimed_job_exhausted(
        job_id=exhausted.id,
        lease_token=first_claim_by_id[exhausted.id].lease_token,
        checked_at=NOW,
        resolution="not_found",
        failure_category=None,
    )
    due_job = job_repository(db_session).get_by_id(still_due.id)
    due_job.state = "pending"
    due_job.lease_token = None
    due_job.lease_expires_at = None
    db_session.add(due_job)
    db_session.commit()

    later_claims = job_repository(db_session).claim_due_jobs(
        now=NOW + timedelta(hours=1),
        lease_seconds=60,
        limit=10,
    )

    assert [claim.id for claim in later_claims] == [still_due.id]
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(resolved.id).state == "resolved"
    assert job_repository(db_session).get_by_id(exhausted.id).state == "exhausted"


def test_automatic_worker_found_order_resolves_job_recovers_attempt_and_does_not_mutate_paper(
    db_session,
    bot_stack_factory,
    funded_account,
    monkeypatch,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    query_calls = []
    post_calls = []

    def query_once(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={"symbol": "BTCUSDT", "orderId": 123, "clientOrderId": f"tap_{bot.id}_now", "status": "FILLED"},
        )

    def fail_if_post_called(self, params):
        post_calls.append(params)
        raise AssertionError("Automatic reconciliation must not submit Binance orders")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_once)
    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_post_called)

    summary = worker_service(db_session, now=NOW).process_due_batch(limit=10)

    assert summary.claimed_count == 1
    assert summary.resolved_count == 1
    assert summary.results[0].resolution == "found"
    assert len(query_calls) == 1
    assert query_calls[0]["origClientOrderId"] == f"tap_{bot.id}_now"
    assert post_calls == []
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "resolved"
    assert updated_job.lease_token is None
    assert updated_job.automatic_attempt_count == 1
    assert updated_attempt.final_status == "order_created"
    assert updated_attempt.final_reason == "testnet_order_recovered_after_unknown_submission"
    assert updated_attempt.metadata_["submission_recovered"] is True
    assert updated_attempt.metadata_["reconciliation_resolution"] == "found"
    assert updated_attempt.metadata_["automatic_reconciliation_last_resolution"] == "found"
    assert updated_attempt.metadata_["exchange_order_id"] == "123"
    serialized = str(updated_attempt.metadata_)
    assert "signature" not in serialized.lower()
    assert "X-MBX-APIKEY" not in serialized
    repository = PortfolioRepository(db_session)
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before


def test_automatic_worker_single_job_call_processes_at_most_one_due_job(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    first_job = add_job(db_session, bot.id, NOW - timedelta(minutes=2))
    second_job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    query_calls = []

    def query_once(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 123,
                "clientOrderId": params["origClientOrderId"],
                "status": "FILLED",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_once)

    summary = worker_service(
        db_session,
        now=NOW,
        settings=worker_settings(batch_size=10),
    ).process_due_job()

    assert summary.claimed_count == 1
    assert summary.processed_count == 1
    assert summary.resolved_count == 1
    assert len(query_calls) == 1
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(first_job.id).state == "resolved"
    assert job_repository(db_session).get_by_id(second_job.id).state == "pending"


def test_automatic_worker_single_job_call_no_due_job_returns_safe_noop(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    future_job = add_job(db_session, bot.id, NOW + timedelta(minutes=5))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("No due automatic reconciliation job must not query Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)

    summary = worker_service(db_session, now=NOW).process_due_job()

    assert summary.claimed_count == 0
    assert summary.processed_count == 0
    assert summary.resolved_count == 0
    assert summary.retried_count == 0
    assert summary.exhausted_count == 0
    assert summary.stale_count == 0
    assert summary.results == []
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(future_job.id).state == "pending"


def test_automatic_worker_not_found_retries_then_exhausts_at_limit(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    current_now = [NOW]
    query_calls = []

    def query_not_found(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)
    service = worker_service(
        db_session,
        now_provider=lambda: current_now[0],
        settings=worker_settings(max_attempts=2, retry_delay=30),
    )

    first = service.process_due_batch(limit=10)
    current_now[0] = NOW + timedelta(seconds=31)
    second = service.process_due_batch(limit=10)

    assert first.retried_count == 1
    assert second.exhausted_count == 1
    assert len(query_calls) == 2
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "exhausted"
    assert updated_job.automatic_attempt_count == 2
    assert updated_job.last_resolution == "not_found"
    assert updated_attempt.final_reason == "testnet_order_reconciliation_unresolved"
    assert updated_attempt.metadata_["submission_recovered"] is False
    assert updated_attempt.metadata_["automatic_reconciliation_last_resolution"] == "not_found"
    assert "NO_SUCH_ORDER" not in str(updated_attempt.metadata_)


def test_automatic_worker_retryable_failure_reschedules_before_limit(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    query_calls = []

    def query_timeout(self, params):
        query_calls.append(params)
        raise BinanceTestnetOrderQueryClientError("raw signed URL timed out", trigger="timeout")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_timeout)

    summary = worker_service(
        db_session,
        now=NOW,
        settings=worker_settings(max_attempts=3, retry_delay=45),
    ).process_due_batch(limit=10)

    assert summary.retried_count == 1
    assert len(query_calls) == 1
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "pending"
    assert updated_job.next_attempt_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=45)
    assert updated_job.automatic_attempt_count == 1
    assert updated_job.last_failure_category == "timeout"
    assert "raw signed URL" not in str(updated_attempt.metadata_)
    assert updated_attempt.metadata_["automatic_reconciliation_last_failure_category"] == "timeout"


def test_automatic_worker_max_attempts_one_exhausts_after_first_processing_attempt(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    query_calls = []

    def query_not_found(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)

    summary = worker_service(
        db_session,
        now=NOW,
        settings=worker_settings(max_attempts=1, retry_delay=45),
    ).process_due_batch(limit=10)

    assert summary.exhausted_count == 1
    assert summary.retried_count == 0
    assert len(query_calls) == 1
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    assert updated_job.state == "exhausted"
    assert updated_job.automatic_attempt_count == 1
    assert updated_job.lease_token is None


def test_automatic_worker_stale_token_cannot_query_or_overwrite_new_claim(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    old_claim = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=1, limit=1)[0]
    new_claim = job_repository(db_session).claim_due_jobs(now=NOW + timedelta(seconds=2), lease_seconds=60, limit=1)[0]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Stale automatic worker must not query Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)

    result = worker_service(db_session, now=NOW + timedelta(seconds=2))._process_claimed_job(old_claim)

    assert result.outcome == "stale"
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "claimed"
    assert updated_job.lease_token == new_claim.lease_token
    assert updated_attempt.final_reason == "testnet_order_reconciliation_unresolved"


def test_automatic_worker_inflight_get_with_replaced_lease_cannot_overwrite_state(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))
    replacement = {}
    query_calls = []

    def query_after_reclaim(self, params):
        query_calls.append(params)
        current = job_repository(db_session).get_by_id(job.id)
        current.lease_expires_at = NOW - timedelta(seconds=1)
        db_session.add(current)
        db_session.commit()
        replacement["claim"] = job_repository(db_session).claim_due_jobs(
            now=NOW + timedelta(seconds=2),
            lease_seconds=60,
            limit=1,
        )[0]
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={"symbol": "BTCUSDT", "orderId": 321, "clientOrderId": f"tap_{bot.id}_now", "status": "FILLED"},
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_after_reclaim)

    summary = worker_service(db_session, now=NOW).process_due_batch(limit=10)

    assert summary.stale_count == 1
    assert len(query_calls) == 1
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(job.execution_attempt_id)
    assert updated_job.state == "claimed"
    assert updated_job.lease_token == replacement["claim"].lease_token
    assert updated_job.automatic_attempt_count == 0
    assert updated_attempt.final_reason == "testnet_order_reconciliation_unresolved"
    assert updated_attempt.metadata_["submission_recovered"] is False
    assert "automatic_reconciliation_last_resolution" not in updated_attempt.metadata_
    assert "321" not in str(updated_attempt.metadata_)


def test_automatic_worker_ineligible_linked_attempt_exhausts_without_http_or_attempt_rewrite(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=True, execution_mode="paper")
    attempt = add_attempt(
        db_session,
        bot_id=bot.id,
        mode="paper",
        broker="paper",
        final_status="rejected_by_broker",
        final_reason="paper_rejected",
        metadata={"client_order_id": "paper_client_id", "keep": "unchanged"},
    )
    job = job_repository(db_session).create_pending(
        execution_attempt_id=attempt.id,
        bot_id=bot.id,
        next_attempt_at=NOW,
    )
    db_session.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Ineligible linked attempts must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)

    summary = worker_service(db_session, now=NOW).process_due_batch(limit=10)

    assert summary.exhausted_count == 1
    assert summary.results[0].failure_category == "wrong_mode_or_broker"
    db_session.expire_all()
    updated_job = job_repository(db_session).get_by_id(job.id)
    updated_attempt = ExecutionAttemptRepository(db_session).get_by_id(attempt.id)
    assert updated_job.state == "exhausted"
    assert updated_job.last_failure_category == "wrong_mode_or_broker"
    assert updated_attempt.metadata_ == {"client_order_id": "paper_client_id", "keep": "unchanged"}


def test_automatic_worker_already_recovered_attempt_resolves_without_http(db_session, bot_stack_factory, monkeypatch) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(
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
            "recovered_order_status": "FILLED",
            "exchange_order_id": "12345",
        },
    )
    job = job_repository(db_session).create_pending(
        execution_attempt_id=attempt.id,
        bot_id=bot.id,
        next_attempt_at=NOW,
    )
    db_session.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Already recovered automatic reconciliation must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)

    summary = worker_service(db_session, now=NOW).process_due_batch(limit=10)

    assert summary.resolved_count == 1
    assert summary.results[0].resolution == "already_resolved"
    db_session.expire_all()
    assert job_repository(db_session).get_by_id(job.id).state == "resolved"
    assert ExecutionAttemptRepository(db_session).get_by_id(attempt.id).metadata_["exchange_order_id"] == "12345"


def test_automatic_worker_public_status_remains_safe_after_retry(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW - timedelta(minutes=1))

    def query_not_found(self, params):
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw payload"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_not_found)
    summary = worker_service(db_session, now=NOW, settings=worker_settings(max_attempts=3)).process_due_batch(limit=10)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status", params={"limit": 10})

    assert summary.retried_count == 1
    assert response.status_code == 200
    assert "lease_token" not in str(summary)
    assert "lease_token" not in response.text
    assert "client_order_id" not in response.text
    assert "new_client_order_id" not in response.text
    assert f"tap_{bot.id}_now" not in response.text
    assert "NO_SUCH_ORDER" not in response.text
    assert "raw payload" not in response.text
    assert "signature" not in response.text.lower()
    body = response.json()
    recent = next(item for item in body["recent_attempts"] if item["attempt_id"] == job.execution_attempt_id)
    assert recent["delayed_reconciliation_state"] == "pending"
    assert recent["delayed_reconciliation_automatic_attempt_count"] == 1
    assert recent["delayed_reconciliation_last_resolution"] == "not_found"


def test_reconciliation_job_audit_list_returns_newest_jobs_and_status_filter(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    old_pending = add_job(db_session, bot.id, NOW - timedelta(minutes=30))
    middle_pending = add_job(db_session, bot.id, NOW - timedelta(minutes=20))
    newest_claimed = add_job(db_session, bot.id, NOW - timedelta(minutes=10))
    for job, created_at in (
        (old_pending, NOW - timedelta(hours=3)),
        (middle_pending, NOW - timedelta(hours=2)),
        (newest_claimed, NOW - timedelta(hours=1)),
    ):
        job.created_at = created_at
        job.updated_at = created_at
        db_session.add(job)
    db_session.commit()
    claimed_job = job_repository(db_session).get_by_id(newest_claimed.id)
    claimed_job.state = "claimed"
    claimed_job.lease_token = "safe-test-claim-token"
    claimed_job.lease_expires_at = NOW + timedelta(minutes=1)
    claimed_job.created_at = NOW - timedelta(hours=1)
    claimed_job.updated_at = NOW - timedelta(minutes=1)
    db_session.add(claimed_job)
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-reconciliation-jobs")
        pending_response = client.get("/api/v1/execution-reconciliation-jobs", params={"status": "pending"})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [newest_claimed.id, middle_pending.id, old_pending.id]
    assert body[0]["status"] == "claimed"
    assert body[0]["claimed_at"].startswith("2026-06-08T11:59:00")
    assert body[0]["max_automatic_attempts"] == 5
    assert "lease_token" not in response.text
    assert "safe-test-claim-token" not in response.text

    assert pending_response.status_code == 200
    pending_body = pending_response.json()
    assert [item["id"] for item in pending_body] == [middle_pending.id, old_pending.id]
    assert all(item["status"] == "pending" for item in pending_body)


def test_reconciliation_job_audit_detail_returns_safe_existing_job(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)
    claimed = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=1)[0]
    job_repository(db_session).mark_claimed_job_resolved(
        job_id=job.id,
        lease_token=claimed.lease_token,
        checked_at=NOW + timedelta(minutes=1),
        resolution="found",
    )
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/execution-reconciliation-jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job.id
    assert body["execution_attempt_id"] == job.execution_attempt_id
    assert body["bot_id"] == bot.id
    assert body["status"] == "resolved"
    assert body["automatic_attempt_count"] == 1
    assert body["max_automatic_attempts"] == 5
    assert body["next_attempt_at"] == job.next_attempt_at.isoformat()
    assert body["claimed_at"] is None
    assert body["resolved_at"].startswith("2026-06-08T12:01:00")
    assert body["exhausted_at"] is None
    assert body["last_result"] == "found"
    assert body["last_failure"] is None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None
    assert "lease_token" not in response.text


def test_reconciliation_job_audit_detail_returns_404_for_missing_job(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        missing_response = client.get("/api/v1/execution-reconciliation-jobs/999999")

    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "execution_reconciliation_job_not_found"


def test_reconciliation_job_audit_list_limit_validation(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        zero_limit_response = client.get("/api/v1/execution-reconciliation-jobs", params={"limit": 0})
        too_large_limit_response = client.get("/api/v1/execution-reconciliation-jobs", params={"limit": 101})
        invalid_status_response = client.get("/api/v1/execution-reconciliation-jobs", params={"status": "running"})

    assert zero_limit_response.status_code == 422
    assert too_large_limit_response.status_code == 422
    assert invalid_status_response.status_code == 422


def test_reconciliation_job_audit_response_excludes_sensitive_fields(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(
        db_session,
        bot_id=bot.id,
        metadata={
            "client_order_id": "tap_sensitive_client",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
            "api_key": "unsafe-api-key",
            "api_secret": "unsafe-api-secret",
            "signature": "unsafe-signature",
            "signed_params": {"signature": "unsafe-signature"},
            "headers": {"X-MBX-APIKEY": "unsafe-api-key"},
            "raw_payload": {"msg": "NO_SUCH_ORDER raw payload"},
        },
    )
    job = job_repository(db_session).create_pending(
        execution_attempt_id=attempt.id,
        bot_id=bot.id,
        next_attempt_at=NOW,
    )
    job.lease_token = "unsafe-lease-token"
    job.lease_expires_at = NOW + timedelta(minutes=1)
    job.state = "claimed"
    job.last_resolution = "symbol=BTCUSDT&signature=unsafe-signature"
    job.last_failure_category = "unsafe-api-secret signed params headers"
    db_session.add(job)
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        list_response = client.get("/api/v1/execution-reconciliation-jobs")
        detail_response = client.get(f"/api/v1/execution-reconciliation-jobs/{job.id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    for response in (list_response, detail_response):
        body = response.json()
        first = body[0] if isinstance(body, list) else body
        serialized = response.text
        assert "last_result" in serialized
        assert "last_failure" in serialized
        assert first["last_result"] == "other"
        assert first["last_failure"] == "other"
        assert "lease_token" not in serialized
        assert "unsafe-lease-token" not in serialized
        assert "unsafe-api-key" not in serialized
        assert "unsafe-api-secret" not in serialized
        assert "unsafe-signature" not in serialized
        assert "signature" not in serialized.lower()
        assert "signed_params" not in serialized
        assert "headers" not in serialized
        assert "X-MBX-APIKEY" not in serialized
        assert "raw_payload" not in serialized
        assert "NO_SUCH_ORDER raw payload" not in serialized
        assert "tap_sensitive_client" not in serialized


def test_reconciliation_job_audit_response_includes_only_safe_fields(
    db_session,
    bot_stack_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        list_response = client.get("/api/v1/execution-reconciliation-jobs")
        detail_response = client.get(f"/api/v1/execution-reconciliation-jobs/{job.id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert set(list_response.json()[0]) == RECONCILIATION_JOB_AUDIT_FIELDS
    assert set(detail_response.json()) == RECONCILIATION_JOB_AUDIT_FIELDS


def test_reconciliation_job_audit_endpoints_are_read_only(
    db_session,
    bot_stack_factory,
    funded_account,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    funded_account(db_session)
    repository = PortfolioRepository(db_session)
    account_before = repository.get_account().cash_balance
    orders_before = repository.list_orders()
    fills_before = repository.list_fills()
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    job = add_job(db_session, bot.id, NOW)
    claimed = job_repository(db_session).claim_due_jobs(now=NOW, lease_seconds=60, limit=1)[0]
    before = job_snapshot(job_repository(db_session).get_by_id(job.id))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Read-only reconciliation-job audit endpoints must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        list_response = client.get("/api/v1/execution-reconciliation-jobs")
        detail_response = client.get(f"/api/v1/execution-reconciliation-jobs/{job.id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    db_session.expire_all()
    assert job_snapshot(job_repository(db_session).get_by_id(job.id)) == before
    assert job_repository(db_session).get_by_id(job.id).lease_token == claimed.lease_token
    assert repository.list_orders() == orders_before
    assert repository.list_fills() == fills_before
    assert repository.get_account().cash_balance == account_before


def job_repository(db_session) -> ExecutionReconciliationJobRepository:
    return ExecutionReconciliationJobRepository(db_session)


def job_service(db_session, *, now=NOW) -> ExecutionReconciliationJobService:
    return ExecutionReconciliationJobService(
        ExecutionAttemptRepository(db_session),
        job_repository(db_session),
        now_provider=lambda: now,
    )


def add_pending_job(db_session, bot_id: int, next_attempt_at: datetime) -> ExecutionReconciliationJob:
    attempt = add_attempt(db_session, bot_id=bot_id)
    job = job_service(db_session).ensure_pending_job_for_attempt(
        execution_attempt_id=attempt.id,
        next_attempt_at=next_attempt_at,
    ).job
    db_session.commit()
    return job


def add_job(db_session, bot_id: int, next_attempt_at: datetime) -> ExecutionReconciliationJob:
    return add_pending_job(db_session, bot_id, next_attempt_at)


def add_claimed_job(
    db_session,
    bot_id: int,
    next_attempt_at: datetime,
    *,
    now: datetime = NOW,
    lease_seconds: int = 60,
    lease_expires_at: datetime | None = None,
):
    job = add_job(db_session, bot_id, next_attempt_at)
    claimed = job_repository(db_session).claim_due_jobs(now=now, lease_seconds=lease_seconds, limit=1)[0]
    assert claimed.id == job.id
    if lease_expires_at is not None:
        stored = job_repository(db_session).get_by_id(job.id)
        stored.lease_expires_at = lease_expires_at
        db_session.add(stored)
        db_session.commit()
    return job, claimed


def add_expired_claimed_job(
    db_session,
    bot_id: int,
    next_attempt_at: datetime,
    *,
    now: datetime = NOW,
):
    return add_claimed_job(
        db_session,
        bot_id,
        next_attempt_at,
        now=now,
        lease_seconds=60,
        lease_expires_at=now - timedelta(seconds=1),
    )


def add_resolved_job(
    db_session,
    bot_id: int,
    next_attempt_at: datetime,
    *,
    now: datetime = NOW,
) -> ExecutionReconciliationJob:
    job, claimed = add_claimed_job(db_session, bot_id, next_attempt_at, now=now)
    job_repository(db_session).mark_claimed_job_resolved(
        job_id=job.id,
        lease_token=claimed.lease_token,
        checked_at=now,
        resolution="found",
    )
    db_session.commit()
    return job


def add_exhausted_job(
    db_session,
    bot_id: int,
    next_attempt_at: datetime,
    *,
    now: datetime = NOW,
    resolution: str = "not_found",
    failure_category: str | None = None,
) -> ExecutionReconciliationJob:
    job, claimed = add_claimed_job(db_session, bot_id, next_attempt_at, now=now)
    job_repository(db_session).mark_claimed_job_exhausted(
        job_id=job.id,
        lease_token=claimed.lease_token,
        checked_at=now,
        resolution=resolution,
        failure_category=failure_category,
    )
    db_session.commit()
    return job


def job_snapshot(job: ExecutionReconciliationJob) -> dict:
    return {
        "state": job.state,
        "next_attempt_at": job.next_attempt_at,
        "lease_token": job.lease_token,
        "lease_expires_at": job.lease_expires_at,
        "automatic_attempt_count": job.automatic_attempt_count,
        "last_checked_at": job.last_checked_at,
        "last_resolution": job.last_resolution,
        "last_failure_category": job.last_failure_category,
        "resolved_at": job.resolved_at,
    }


def settings_with_delay(monkeypatch, *, delay: int):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "binance_testnet_reconciliation_initial_delay_seconds", delay)
    return settings


def worker_service(
    db_session,
    *,
    now=NOW,
    now_provider=None,
    settings: Settings | None = None,
) -> ExecutionReconciliationWorkerService:
    return ExecutionReconciliationWorkerService(
        ExecutionAttemptRepository(db_session),
        job_repository(db_session),
        settings=settings or worker_settings(),
        timestamp_provider=lambda: 1710000000000,
        now_provider=now_provider or (lambda: now),
    )


def worker_settings(*, max_attempts: int = 5, retry_delay: int = 60, batch_size: int = 10) -> Settings:
    return Settings(
        BINANCE_TESTNET_BROKER_ENABLED=True,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=True,
        BINANCE_TESTNET_BASE_URL="https://testnet.binance.vision",
        BINANCE_TESTNET_API_KEY="test-api-key",
        BINANCE_TESTNET_API_SECRET="test-api-secret",
        BINANCE_TESTNET_RECV_WINDOW=5000,
        BINANCE_TESTNET_TIMEOUT_SECONDS=5,
        BINANCE_TESTNET_RECONCILIATION_INITIAL_DELAY_SECONDS=300,
        BINANCE_TESTNET_RECONCILIATION_LEASE_SECONDS=30,
        BINANCE_TESTNET_RECONCILIATION_RETRY_DELAY_SECONDS=retry_delay,
        BINANCE_TESTNET_RECONCILIATION_MAX_AUTOMATIC_ATTEMPTS=max_attempts,
        BINANCE_TESTNET_RECONCILIATION_BATCH_SIZE=batch_size,
    )
