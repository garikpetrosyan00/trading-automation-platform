import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.portfolio import PortfolioRepository


def test_order_audit_lists_orders_after_paper_buy_and_sell_decisions(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    runner = bot_runner_factory()
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    stub_market_data_service.set_price("BTCUSDT", "115")
    asyncio.run(runner.run_cycle())
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/orders")
        bot_response = client.get(f"/api/v1/bots/{bot.id}/orders")
        attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts")
        filtered_response = client.get(
            "/api/v1/orders",
            params={
                "bot_id": bot.id,
                "status": "filled",
                "side": "sell",
                "symbol": "btcusdt",
                "mode": "paper",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["side"] == "sell"
    assert body[0]["bot_id"] == bot.id
    assert body[0]["strategy_id"] == strategy.id
    assert body[0]["order_type"] == "market"
    assert body[0]["mode"] == "paper"
    assert body[0]["status"] == "filled"
    assert body[0]["fill_count"] == 1
    assert body[0]["fills"] == []
    assert body[0]["requested_price"] == "115.00000000"
    assert body[1]["side"] == "buy"

    assert bot_response.status_code == 200
    assert [order["id"] for order in bot_response.json()] == [body[0]["id"], body[1]["id"]]

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert len(attempts) == 2
    assert attempts[0]["side"] == "sell"
    assert attempts[0]["final_status"] == "filled"
    assert attempts[0]["order_id"] == body[0]["id"]
    assert attempts[0]["risk_status"] == "allowed"
    assert attempts[0]["safety_status"] == "allowed"
    assert attempts[1]["side"] == "buy"
    assert attempts[1]["order_id"] == body[1]["id"]

    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert len(filtered) == 1
    assert filtered[0]["id"] == body[0]["id"]


def test_order_audit_retrieves_single_order_and_order_fills(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    runner = bot_runner_factory()
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    order = PortfolioRepository(db_session).list_orders()[0]
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        order_response = client.get(f"/api/v1/orders/{order.id}")
        fills_response = client.get(f"/api/v1/orders/{order.id}/fills")

    assert order_response.status_code == 200
    order_body = order_response.json()
    assert order_body["id"] == order.id
    assert order_body["bot_id"] == bot.id
    assert order_body["side"] == "buy"
    assert order_body["decision_reason"] == "price is below strategy buy_below"
    assert order_body["decision_metadata"]["decision"] == "buy"
    assert order_body["fill_count"] == 1
    assert len(order_body["fills"]) == 1

    assert fills_response.status_code == 200
    fills = fills_response.json()
    assert len(fills) == 1
    assert fills[0]["order_id"] == order.id
    assert fills[0]["fill_price"] == "95.00000000"
    assert fills[0]["fill_quantity"] == "0.10000000"
    assert fills[0]["fee"] == "0E-8"
    assert fills[0]["source"] == "paper"
    assert fills[0]["filled_at"] is not None


def test_rejected_order_audit_appears_without_fill(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session, amount=Decimal("100"))
    stub_market_data_service.set_price("BTCUSDT", "50000")
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        orders_response = client.get("/api/v1/orders", params={"status": "rejected"})

    assert create_response.status_code == 200
    assert create_response.json()["accepted"] is False
    assert create_response.json()["fill"] is None

    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert len(orders) == 1
    assert orders[0]["status"] == "rejected"
    assert orders[0]["fill_count"] == 0
    assert orders[0]["rejection_reason"] == "insufficient_paper_cash"


def test_risk_blocked_and_live_mode_create_no_audit_orders(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session)
    _, risk_blocked_bot, profile = bot_stack_factory(db_session, name="Risk Blocked Bot")
    assert profile is not None
    profile.max_trade_quantity = Decimal("0.05")
    _, live_bot, _ = bot_stack_factory(db_session, name="Live Bot", is_paper=False)
    db_session.add(profile)
    db_session.commit()

    runner = bot_runner_factory()
    runner.start_bot(risk_blocked_bot.id)
    runner.start_bot(live_bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_cycle())
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        risk_response = client.get(f"/api/v1/bots/{risk_blocked_bot.id}/orders")
        live_response = client.get(f"/api/v1/bots/{live_bot.id}/orders")
        risk_attempt_response = client.get(
            f"/api/v1/bots/{risk_blocked_bot.id}/execution-attempts",
            params={"final_status": "blocked_by_risk", "limit": 1},
        )
        live_attempt_response = client.get(
            f"/api/v1/bots/{live_bot.id}/execution-attempts",
            params={"final_status": "blocked_by_safety", "limit": 1},
        )

    assert risk_response.status_code == 200
    assert risk_response.json() == []
    assert live_response.status_code == 200
    assert live_response.json() == []

    assert risk_attempt_response.status_code == 200
    risk_attempts = risk_attempt_response.json()
    assert len(risk_attempts) == 1
    assert risk_attempts[0]["final_status"] == "blocked_by_risk"
    assert risk_attempts[0]["final_reason"] == "max_trade_quantity_exceeded"
    assert risk_attempts[0]["order_id"] is None

    assert live_attempt_response.status_code == 200
    live_attempts = live_attempt_response.json()
    assert len(live_attempts) == 1
    assert live_attempts[0]["mode"] == "live"
    assert live_attempts[0]["final_status"] == "blocked_by_safety"
    assert live_attempts[0]["final_reason"] == "live_mode_not_implemented"
    assert live_attempts[0]["order_id"] is None


def test_hold_decision_creates_no_execution_attempt(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    runner = bot_runner_factory()
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "105")
    asyncio.run(runner.run_cycle())
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts")

    assert response.status_code == 200
    assert response.json() == []


def test_execution_attempt_public_metadata_redacts_internal_identifiers_recursively(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    attempt = ExecutionAttempt(
        bot_id=bot.id,
        strategy_id=None,
        order_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=Decimal("0.001"),
        requested_price=Decimal("100"),
        decision_reason="test public metadata redaction",
        risk_status="allowed",
        safety_status="allowed",
        final_status="order_created",
        final_reason="binance_testnet_order_created",
        metadata_={
            "client_order_id": "tap_internal_client",
            "exchange_order_id": "98765",
            "exchange_client_order_id": "tap_exchange_client",
            "origClientOrderId": "tap_orig",
            "orderId": 98765,
            "newClientOrderId": "tap_new",
            "lease_token": "unsafe-lease-token",
            "signature": "unsafe-signature",
            "api_key": "unsafe-api-key",
            "api_secret": "unsafe-api-secret",
            "headers": {"X-MBX-APIKEY": "unsafe-api-key"},
            "signed_query": "symbol=BTCUSDT&signature=unsafe-signature",
            "raw_response": {"orderId": 98765},
            "raw_payload": {"client_order_id": "nested-client"},
            "exchange_status": "FILLED",
            "dry_run": False,
            "status_code": 200,
            "nested": {
                "client_order_id": "nested-client",
                "status_code": 201,
                "items": [
                    {"orderId": 1, "exchange_status": "NEW"},
                    {"headers": {"X-MBX-APIKEY": "unsafe"}, "dry_run": True},
                ],
            },
        },
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        list_response = client.get("/api/v1/execution-attempts")
        bot_list_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts")
        detail_response = client.get(f"/api/v1/execution-attempts/{attempt.id}")

    assert list_response.status_code == 200
    assert bot_list_response.status_code == 200
    assert detail_response.status_code == 200
    for body in (list_response.json()[0], bot_list_response.json()[0], detail_response.json()):
        metadata = body["metadata"]
        assert metadata["exchange_status"] == "FILLED"
        assert metadata["dry_run"] is False
        assert metadata["status_code"] == 200
        assert metadata["nested"]["status_code"] == 201
        assert metadata["nested"]["items"][0] == {"exchange_status": "NEW"}
        assert metadata["nested"]["items"][1] == {"dry_run": True}

    serialized = detail_response.text
    for hidden in (
        "client_order_id",
        "exchange_order_id",
        "exchange_client_order_id",
        "origClientOrderId",
        "orderId",
        "newClientOrderId",
        "lease_token",
        "signature",
        "api_key",
        "api_secret",
        "headers",
        "signed_query",
        "raw_response",
        "raw_payload",
        "unsafe-api-key",
        "unsafe-signature",
        "tap_internal_client",
        "tap_exchange_client",
    ):
        assert hidden not in serialized

    db_session.expire_all()
    persisted = ExecutionAttemptRepository(db_session).get_by_id(attempt.id)
    assert persisted.metadata_["client_order_id"] == "tap_internal_client"
    assert persisted.metadata_["exchange_order_id"] == "98765"
    assert persisted.metadata_["exchange_client_order_id"] == "tap_exchange_client"


def test_public_schemas_do_not_expose_internal_reconciliation_identifier_fields(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    assert "new_client_order_id" not in schemas["ExecutionReconciliationAttemptRead"]["properties"]
    assert "binance_order_id" not in schemas["ExecutionReconciliationAttemptRead"]["properties"]
    assert "new_client_order_id" not in schemas["ExecutionManualReconciliationRead"]["properties"]
    assert "exchange_order_id" not in schemas["ExecutionManualReconciliationRead"]["properties"]


def test_order_audit_unknown_order_and_limit_validation(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        missing_response = client.get("/api/v1/orders/999999")
        missing_attempt_response = client.get("/api/v1/execution-attempts/999999")
        too_large_limit_response = client.get("/api/v1/orders", params={"limit": 101})
        too_large_attempt_limit_response = client.get("/api/v1/execution-attempts", params={"limit": 101})
        invalid_filter_response = client.get("/api/v1/orders", params={"side": "hold"})
        invalid_attempt_filter_response = client.get("/api/v1/execution-attempts", params={"final_status": "nope"})

    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "order_not_found"
    assert missing_attempt_response.status_code == 404
    assert missing_attempt_response.json()["error_code"] == "execution_attempt_not_found"
    assert too_large_limit_response.status_code == 422
    assert too_large_attempt_limit_response.status_code == 422
    assert invalid_filter_response.status_code == 422
    assert invalid_attempt_filter_response.status_code == 422
