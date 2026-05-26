import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
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
    assert orders[0]["rejection_reason"] == "Insufficient cash balance for this buy order"


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

    assert risk_response.status_code == 200
    assert risk_response.json() == []
    assert live_response.status_code == 200
    assert live_response.json() == []


def test_order_audit_unknown_order_and_limit_validation(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        missing_response = client.get("/api/v1/orders/999999")
        too_large_limit_response = client.get("/api/v1/orders", params={"limit": 101})
        invalid_filter_response = client.get("/api/v1/orders", params={"side": "hold"})

    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "order_not_found"
    assert too_large_limit_response.status_code == 422
    assert invalid_filter_response.status_code == 422
