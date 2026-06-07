from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import (
    BinanceInvalidOrderQueryResponseError,
    BinanceOrderHttpResponse,
    BinanceTestnetOrderClient,
    BinanceTestnetOrderQueryClientError,
)
from app.services.execution_reconciliation import ExecutionReconciliationStatusService

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
        "pending_delayed_reconciliation_count": 0,
        "claimed_delayed_reconciliation_count": 0,
        "expired_lease_count": 0,
        "exhausted_delayed_reconciliation_count": 0,
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
        "delayed_reconciliation_job_id": None,
        "delayed_reconciliation_state": None,
        "delayed_reconciliation_next_attempt_at": None,
        "delayed_reconciliation_lease_expires_at": None,
        "delayed_reconciliation_automatic_attempt_count": None,
        "delayed_reconciliation_last_checked_at": None,
        "delayed_reconciliation_last_resolution": None,
        "delayed_reconciliation_last_failure_category": None,
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


def test_manual_reconciliation_missing_bot_and_attempt_return_existing_404_style(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        missing_bot_response = client.post("/api/v1/bots/999999/execution-attempts/1/reconcile")
        missing_attempt_response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/999999/reconcile")

    assert missing_bot_response.status_code == 404
    assert missing_bot_response.json()["error_code"] == "bot_not_found"
    assert missing_attempt_response.status_code == 404
    assert missing_attempt_response.json()["error_code"] == "execution_attempt_not_found"


def test_manual_reconciliation_signed_get_uses_persisted_identifiers(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(
        db_session,
        bot_id=bot.id,
        metadata={
            "client_order_id": "tap_original_client_id",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": "timeout",
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
        },
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        captured["query"] = parse_qs(request.url.query.decode())
        return httpx.Response(
            200,
            json={
                "symbol": "BTCUSDT",
                "orderId": 123456,
                "clientOrderId": "tap_original_client_id",
                "status": "FILLED",
            },
        )

    settings = enabled_testnet_settings()
    order_client = BinanceTestnetOrderClient(
        base_url=settings.binance_testnet_base_url,
        api_key=settings.binance_testnet_api_key or "",
        transport=httpx.MockTransport(handler),
    )
    service = ExecutionReconciliationStatusService(
        ExecutionAttemptRepository(db_session),
        settings=settings,
        order_client=order_client,
        timestamp_provider=lambda: 1710000000000,
    )

    response = service.manually_reconcile_attempt(bot_id=bot.id, attempt_id=attempt.id)

    assert response.submission_recovered is True
    assert response.reconciliation_resolution == "found"
    assert response.recovered_order_status == "FILLED"
    assert response.exchange_order_id == "123456"
    assert captured["method"] == "GET"
    assert captured["path"] == "/api/v3/order"
    assert captured["api_key"] == "test-api-key"
    assert captured["query"]["symbol"] == ["BTCUSDT"]
    assert captured["query"]["origClientOrderId"] == ["tap_original_client_id"]
    assert captured["query"]["recvWindow"] == ["5000"]
    assert captured["query"]["timestamp"] == ["1710000000000"]
    assert "signature" in captured["query"]


def test_manual_reconciliation_success_updates_existing_attempt_and_observability(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    monkeypatch,
) -> None:
    set_testnet_settings(monkeypatch)
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(
        db_session,
        bot_id=bot.id,
        metadata={
            "client_order_id": "tap_manual_success",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": "http_5xx",
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
            "api_key": API_KEY,
            "signature": "unsafe-signature",
        },
    )
    post_calls = []
    query_calls = []

    def fail_if_post_called(self, params):
        post_calls.append(params)
        raise AssertionError("Manual reconciliation must not submit Binance orders")

    def query_once(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 999,
                "clientOrderId": "tap_manual_success",
                "status": "NEW",
            },
        )

    monkeypatch.setattr(BinanceTestnetOrderClient, "submit_signed_market_order", fail_if_post_called)
    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_once)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile")
        status_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert response.status_code == 200
    body = response.json()
    assert body["already_resolved"] is False
    assert body["submission_status_unknown"] is True
    assert body["submission_recovered"] is True
    assert body["reconciliation_resolution"] == "found"
    assert body["recovered_order_status"] == "NEW"
    assert body["exchange_order_id"] == "999"
    assert body["new_client_order_id"] == "tap_manual_success"
    assert body["manual_reconciliation_attempted"] is True
    assert body["manual_reconciliation_attempt_count"] == 1
    assert body["manual_reconciliation_last_resolution"] == "found"
    assert body["manual_reconciliation_last_failure_category"] is None
    assert len(query_calls) == 1
    assert post_calls == []

    db_session.expire_all()
    updated = ExecutionAttemptRepository(db_session).get_by_id(attempt.id)
    assert updated.final_status == "order_created"
    assert updated.final_reason == "testnet_order_recovered_after_unknown_submission"
    assert updated.metadata_["reconciliation_trigger"] == "http_5xx"
    assert updated.metadata_["manual_reconciliation_attempt_count"] == 1
    assert updated.metadata_["manual_reconciliation_last_resolution"] == "found"
    serialized_metadata = str(updated.metadata_)
    assert API_KEY not in serialized_metadata
    assert "unsafe-signature" not in serialized_metadata

    status_body = status_response.json()
    assert status_body["unresolved_unknown_count"] == 0
    assert status_body["recovered_count"] == 1
    assert status_body["latest_recovered_at"] == updated.created_at.isoformat()
    assert status_body["recent_attempts"][0]["submission_recovered"] is True
    assert "metadata" not in status_response.text
    repository = PortfolioRepository(db_session)
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before


def test_manual_reconciliation_already_recovered_is_idempotent_without_http(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    set_testnet_settings(monkeypatch)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(
        db_session,
        bot_id=bot.id,
        final_status="order_created",
        final_reason="testnet_order_recovered_after_unknown_submission",
        metadata={
            "client_order_id": "tap_already_recovered",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "found",
            "submission_recovered": True,
            "recovered_order_status": "FILLED",
            "exchange_order_id": "12345",
            "manual_reconciliation_attempt_count": 2,
        },
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Already recovered attempts must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile")

    assert response.status_code == 200
    assert response.json()["already_resolved"] is True
    assert response.json()["submission_recovered"] is True
    assert response.json()["manual_reconciliation_attempt_count"] == 2
    db_session.expire_all()
    assert ExecutionAttemptRepository(db_session).get_by_id(attempt.id).metadata_["manual_reconciliation_attempt_count"] == 2


def test_manual_reconciliation_rejects_non_reconcilable_attempts_without_http(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    set_testnet_settings(monkeypatch)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    _, other_bot, _ = bot_stack_factory(db_session, name="Other Bot", is_paper=False, execution_mode="testnet")
    cases = [
        add_attempt(db_session, bot_id=other_bot.id),
        add_attempt(db_session, bot_id=bot.id, mode="paper", broker="paper"),
        add_attempt(db_session, bot_id=bot.id, final_reason="binance_testnet_order_rejected", metadata={}),
        add_attempt(db_session, bot_id=bot.id, final_status="rejected_by_broker", final_reason="testnet_quantity_below_minimum", metadata={}),
        add_attempt(
            db_session,
            bot_id=bot.id,
            final_reason="testnet_insufficient_balance",
            metadata={"account_preflight_checked": True},
        ),
        add_attempt(
            db_session,
            bot_id=bot.id,
            final_reason="testnet_order_submission_dry_run",
            metadata={"client_order_id": "tap_dry_run", "dry_run": True},
        ),
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

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Non-reconcilable attempts must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        responses = [client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile") for attempt in cases]

    assert all(response.status_code == 409 for response in responses)
    assert all(response.json()["error_code"] == "execution_attempt_not_reconcilable" for response in responses)


def test_manual_reconciliation_not_found_keeps_attempt_unresolved(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    set_testnet_settings(monkeypatch)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(db_session, bot_id=bot.id)
    query_calls = []

    def query_once(self, params):
        query_calls.append(params)
        return BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER raw body"})

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_once)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile")

    assert response.status_code == 200
    body = response.json()
    assert body["submission_recovered"] is False
    assert body["reconciliation_resolution"] == "unresolved"
    assert body["manual_reconciliation_attempt_count"] == 1
    assert body["manual_reconciliation_last_resolution"] == "not_found"
    assert len(query_calls) == 1
    db_session.expire_all()
    updated = ExecutionAttemptRepository(db_session).get_by_id(attempt.id)
    assert updated.final_reason == "testnet_order_reconciliation_unresolved"
    assert updated.metadata_["submission_recovered"] is False
    assert updated.metadata_["manual_reconciliation_last_resolution"] == "not_found"
    assert "NO_SUCH_ORDER" not in str(updated.metadata_)


def test_manual_reconciliation_query_failures_keep_unresolved_with_safe_category(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    set_testnet_settings(monkeypatch)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    cases = [
        (BinanceTestnetOrderQueryClientError("timeout raw signed url", trigger="timeout"), "timeout"),
        (BinanceTestnetOrderQueryClientError("network raw signed url", trigger="network_error"), "network_error"),
        (BinanceOrderHttpResponse(status_code=500, payload={"msg": "raw response body"}), "http_error"),
        (BinanceInvalidOrderQueryResponseError("raw invalid json"), "invalid_response"),
        (BinanceOrderHttpResponse(status_code=200, payload={"symbol": "BTCUSDT", "status": "NEW"}), "mismatched_response"),
        (
            BinanceOrderHttpResponse(
                status_code=200,
                payload={"symbol": "ETHUSDT", "orderId": 1, "clientOrderId": "tap_failure", "status": "NEW"},
            ),
            "mismatched_response",
        ),
        (
            BinanceOrderHttpResponse(
                status_code=200,
                payload={"symbol": "BTCUSDT", "orderId": 1, "clientOrderId": "different", "status": "NEW"},
            ),
            "mismatched_response",
        ),
    ]

    for index, (result_or_exception, expected_category) in enumerate(cases):
        attempt = add_attempt(
            db_session,
            bot_id=bot.id,
            metadata={
                "client_order_id": "tap_failure",
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_resolution": "unresolved",
                "submission_recovered": False,
            },
        )
        query_calls = []

        def query_once(self, params, result_or_exception=result_or_exception):
            query_calls.append(params)
            if isinstance(result_or_exception, Exception):
                raise result_or_exception
            return result_or_exception

        monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", query_once)
        configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

        with TestClient(app) as client:
            response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile")

        assert response.status_code == 502, index
        assert response.json()["error_code"] == "testnet_reconciliation_query_failed"
        assert len(query_calls) == 1
        db_session.expire_all()
        updated = ExecutionAttemptRepository(db_session).get_by_id(attempt.id)
        assert updated.metadata_["manual_reconciliation_attempt_count"] == 1
        assert updated.metadata_["manual_reconciliation_last_resolution"] == "failed"
        assert updated.metadata_["manual_reconciliation_last_failure_category"] == expected_category
        serialized = str(updated.metadata_)
        assert "raw signed url" not in serialized
        assert "raw response body" not in serialized
        assert "raw invalid json" not in serialized
        assert "signature" not in serialized.lower()
        assert API_KEY not in serialized
        assert API_SECRET not in serialized


def test_manual_reconciliation_config_error_blocks_before_http(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "binance_testnet_broker_enabled", False)
    monkeypatch.setattr(settings, "binance_testnet_order_submission_enabled", True)
    monkeypatch.setattr(settings, "binance_testnet_api_key", "test-api-key")
    monkeypatch.setattr(settings, "binance_testnet_api_secret", "test-api-secret")
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = add_attempt(db_session, bot_id=bot.id)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Misconfigured manual reconciliation must not call Binance")

    monkeypatch.setattr(BinanceTestnetOrderClient, "query_signed_order", fail_if_called)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot.id}/execution-attempts/{attempt.id}/reconcile")

    assert response.status_code == 409
    assert response.json()["error_code"] == "testnet_reconciliation_config_unavailable"
    db_session.expire_all()
    assert ExecutionAttemptRepository(db_session).get_by_id(attempt.id).metadata_.get("manual_reconciliation_attempt_count") is None


def add_attempt(
    session,
    *,
    bot_id: int,
    created_at: datetime | None = None,
    symbol: str = "BTCUSDT",
    mode: str = "testnet",
    broker: str = "binance_testnet",
    final_status: str = "rejected_by_broker",
    final_reason: str = "testnet_order_reconciliation_unresolved",
    metadata=DEFAULT_METADATA,
) -> ExecutionAttempt:
    attempt = ExecutionAttempt(
        bot_id=bot_id,
        strategy_id=None,
        symbol=symbol,
        side="buy",
        mode=mode,
        broker=broker,
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


def enabled_testnet_settings() -> Settings:
    return Settings(
        BINANCE_TESTNET_BROKER_ENABLED=True,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=True,
        BINANCE_TESTNET_BASE_URL="https://testnet.binance.vision",
        BINANCE_TESTNET_API_KEY="test-api-key",
        BINANCE_TESTNET_API_SECRET="test-api-secret",
        BINANCE_TESTNET_RECV_WINDOW=5000,
        BINANCE_TESTNET_TIMEOUT_SECONDS=5,
    )


def set_testnet_settings(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "binance_testnet_broker_enabled", True)
    monkeypatch.setattr(settings, "binance_testnet_order_submission_enabled", True)
    monkeypatch.setattr(settings, "binance_testnet_base_url", "https://testnet.binance.vision")
    monkeypatch.setattr(settings, "binance_testnet_api_key", "test-api-key")
    monkeypatch.setattr(settings, "binance_testnet_api_secret", "test-api-secret")
    monkeypatch.setattr(settings, "binance_testnet_recv_window", 5000)
    monkeypatch.setattr(settings, "binance_testnet_timeout_seconds", 5)
