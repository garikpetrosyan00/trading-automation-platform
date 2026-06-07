from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceTestnetOrderClient

API_KEY = "unsafe-api-key"
API_SECRET = "unsafe-api-secret"
DEFAULT_METADATA = object()


def test_reconciliation_status_empty_for_existing_bot(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert response.status_code == 200
    assert response.json() == {
        "bot_id": bot.id,
        "unresolved_unknown_count": 0,
        "recovered_count": 0,
        "latest_unresolved_at": None,
        "latest_recovered_at": None,
        "recent_attempts": [],
    }


def test_reconciliation_status_missing_bot_returns_existing_404_style(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/bots/999999/execution-reconciliation/status")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_reconciliation_status_normalizes_safe_fields_counts_and_ordering(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    base_time = datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc)
    old_unresolved = add_attempt(
        db_session,
        bot_id=bot.id,
        created_at=base_time - timedelta(minutes=30),
        final_status="rejected_by_broker",
        final_reason="testnet_order_reconciliation_unresolved",
        metadata={
            "client_order_id": "tap_old_unresolved",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": "network_error",
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
            "api_key": API_KEY,
            "api_secret": API_SECRET,
            "signature": "unsafe-signature",
            "signed_query": "symbol=BTCUSDT&signature=unsafe-signature",
            "headers": {"X-MBX-APIKEY": API_KEY},
            "raw_get_body": "unsafe raw body",
            "unsafe_exception": "signed URL leaked",
        },
    )
    recovered = add_attempt(
        db_session,
        bot_id=bot.id,
        created_at=base_time - timedelta(minutes=10),
        final_status="order_created",
        final_reason="testnet_order_recovered_after_unknown_submission",
        metadata={
            "client_order_id": "tap_recovered",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": "timeout",
            "reconciliation_resolution": "found",
            "submission_recovered": True,
            "recovered_order_status": "NEW",
            "exchange_order_id": "12345",
            "raw_post_body": "unsafe raw post",
        },
    )
    latest_unresolved = add_attempt(
        db_session,
        bot_id=bot.id,
        created_at=base_time,
        final_status="rejected_by_broker",
        final_reason="testnet_order_reconciliation_unresolved",
        metadata={
            "client_order_id": "tap_latest_unresolved",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": "http_5xx",
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
        },
    )
    add_attempt(
        db_session,
        bot_id=bot.id,
        created_at=base_time + timedelta(minutes=10),
        final_status="filled",
        final_reason="filled",
        metadata={"client_order_id": "tap_not_reconciliation"},
    )
    add_attempt(
        db_session,
        bot_id=bot.id,
        created_at=base_time + timedelta(minutes=20),
        final_status="rejected_by_broker",
        final_reason="legacy_without_metadata",
        metadata=None,
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert response.status_code == 200
    body = response.json()
    assert body["unresolved_unknown_count"] == 2
    assert body["recovered_count"] == 1
    assert body["latest_unresolved_at"] == latest_unresolved.created_at.isoformat()
    assert body["latest_recovered_at"] == recovered.created_at.isoformat()
    assert [attempt["attempt_id"] for attempt in body["recent_attempts"]] == [
        latest_unresolved.id,
        recovered.id,
        old_unresolved.id,
    ]

    latest = body["recent_attempts"][0]
    assert latest == {
        "attempt_id": latest_unresolved.id,
        "bot_id": bot.id,
        "created_at": latest_unresolved.created_at.isoformat(),
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": "0.10000000",
        "reason": "testnet_order_reconciliation_unresolved",
        "new_client_order_id": "tap_latest_unresolved",
        "submission_status_unknown": True,
        "reconciliation_attempted": True,
        "reconciliation_trigger": "http_5xx",
        "reconciliation_resolution": "unresolved",
        "submission_recovered": False,
        "recovered_order_status": None,
        "binance_order_id": None,
    }

    recovered_body = body["recent_attempts"][1]
    assert recovered_body["submission_recovered"] is True
    assert recovered_body["reconciliation_resolution"] == "found"
    assert recovered_body["recovered_order_status"] == "NEW"
    assert recovered_body["binance_order_id"] == "12345"

    serialized = response.text
    assert "metadata" not in serialized
    assert API_KEY not in serialized
    assert API_SECRET not in serialized
    assert "signature" not in serialized.lower()
    assert "signed_query" not in serialized
    assert "X-MBX-APIKEY" not in serialized
    assert "raw_get_body" not in serialized
    assert "raw_post_body" not in serialized
    assert "signed URL leaked" not in serialized


def test_reconciliation_status_limit_validation_and_bounds(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    base_time = datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc)
    first = add_attempt(db_session, bot_id=bot.id, created_at=base_time - timedelta(minutes=1))
    second = add_attempt(db_session, bot_id=bot.id, created_at=base_time)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        limited_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status", params={"limit": 1})
        zero_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status", params={"limit": 0})
        too_large_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status", params={"limit": 101})

    assert limited_response.status_code == 200
    assert [attempt["attempt_id"] for attempt in limited_response.json()["recent_attempts"]] == [second.id]
    assert first.id != second.id
    assert zero_response.status_code == 422
    assert too_large_response.status_code == 422


def test_reconciliation_status_is_read_only_and_makes_no_binance_calls(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    monkeypatch,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    add_attempt(db_session, bot_id=bot.id)
    attempts_before = len(ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=100))
    orders_before = PortfolioRepository(db_session).list_orders()
    fills_before = PortfolioRepository(db_session).list_fills()

    def fail_if_post_called(*args, **kwargs):
        raise AssertionError("Observability endpoint must not submit Binance orders")

    def fail_if_get_called(*args, **kwargs):
        raise AssertionError("Observability endpoint must not query Binance orders")

    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_post_called)
    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_get_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert response.status_code == 200
    assert len(ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=100)) == attempts_before
    repository = PortfolioRepository(db_session)
    assert repository.list_orders() == orders_before
    assert repository.list_fills() == fills_before
    assert repository.get_account().cash_balance == account_before


def add_attempt(
    session,
    *,
    bot_id: int,
    created_at: datetime | None = None,
    final_status: str = "rejected_by_broker",
    final_reason: str = "testnet_order_reconciliation_unresolved",
    metadata=DEFAULT_METADATA,
) -> ExecutionAttempt:
    attempt = ExecutionAttempt(
        bot_id=bot_id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=Decimal("0.1"),
        requested_price=Decimal("100"),
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status=final_status,
        final_reason=final_reason,
        metadata_=(
            {
                "client_order_id": f"tap_{bot_id}_{created_at.timestamp() if created_at else 'now'}",
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_trigger": "timeout",
                "reconciliation_resolution": "unresolved",
                "submission_recovered": False,
            }
            if metadata is DEFAULT_METADATA
            else metadata
        ),
        created_at=created_at or datetime.now(timezone.utc),
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt
