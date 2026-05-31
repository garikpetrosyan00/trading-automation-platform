from app.main import app
from app.core.config import Settings
from app.repositories.execution_attempt import ExecutionAttemptRepository


def test_portfolio_and_execution_endpoints(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        summary_response = client.get("/api/v1/portfolio/summary")
        paper_snapshot_response = client.get("/api/v1/paper-portfolio")
        positions_response = client.get("/api/v1/portfolio/positions")
        buy_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "0.01"},
        )
        stub_market_data_service.set_price("BTCUSDT", "51000.00")
        sell_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "sell", "quantity": "0.004"},
        )
        orders_response = client.get("/api/v1/execution/orders")
        fills_response = client.get("/api/v1/execution/fills")

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "base_currency": "USD",
        "starting_cash": "10000.00000000",
        "cash_balance": "10000.00000000",
        "market_value": "0",
        "equity": "10000.00000000",
        "unrealized_pnl": "0",
        "realized_pnl": "0",
    }

    assert paper_snapshot_response.status_code == 200
    paper_snapshot = paper_snapshot_response.json()
    assert paper_snapshot["base_currency"] == "USD"
    assert paper_snapshot["starting_balance"] == "10000.00000000"
    assert paper_snapshot["cash_balance"] == "10000.00000000"
    assert paper_snapshot["positions"] == []
    assert paper_snapshot["total_market_value"] == "0"
    assert paper_snapshot["total_unrealized_pnl"] == "0"
    assert paper_snapshot["total_equity"] == "10000.00000000"
    assert paper_snapshot["updated_at"] is not None

    assert positions_response.status_code == 200
    assert positions_response.json() == []

    assert buy_response.status_code == 200
    assert buy_response.json() == {
        "accepted": True,
        "status": "filled",
        "message": "Market buy order filled",
        "order": {
            "id": 1,
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": "0.01000000",
            "requested_price_snapshot": "50000.00000000",
            "status": "filled",
            "rejection_reason": None,
            "created_at": buy_response.json()["order"]["created_at"],
        },
        "fill": {
            "id": 1,
            "order_id": 1,
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": "0.01000000",
            "fill_price": "50025.00000000",
            "fee": "0.50025000",
            "created_at": buy_response.json()["fill"]["created_at"],
        },
        "updated_cash_balance": "9499.24975000",
        "position": {
            "symbol": "BTCUSDT",
            "quantity": "0.01000000",
            "average_entry_price": "50075.02500000",
            "realized_pnl": "0E-8",
        },
    }

    assert sell_response.status_code == 200
    assert sell_response.json() == {
        "accepted": True,
        "status": "filled",
        "message": "Market sell order filled",
        "order": {
            "id": 2,
            "symbol": "BTCUSDT",
            "side": "sell",
            "quantity": "0.00400000",
            "requested_price_snapshot": "51000.00000000",
            "status": "filled",
            "rejection_reason": None,
            "created_at": sell_response.json()["order"]["created_at"],
        },
        "fill": {
            "id": 2,
            "order_id": 2,
            "symbol": "BTCUSDT",
            "side": "sell",
            "quantity": "0.00400000",
            "fill_price": "50974.50000000",
            "fee": "0.20389800",
            "created_at": sell_response.json()["fill"]["created_at"],
        },
        "updated_cash_balance": "9702.94385200",
        "position": {
            "symbol": "BTCUSDT",
            "quantity": "0.00600000",
            "average_entry_price": "50075.02500000",
            "realized_pnl": "3.39400200",
        },
    }

    assert orders_response.status_code == 200
    assert len(orders_response.json()) == 2
    assert orders_response.json()[0]["side"] == "sell"
    assert orders_response.json()[1]["side"] == "buy"

    assert fills_response.status_code == 200
    assert len(fills_response.json()) == 2
    assert fills_response.json()[0]["side"] == "sell"
    assert fills_response.json()[1]["side"] == "buy"


def test_paper_portfolio_reset_endpoint_rejects_open_position_and_succeeds_when_flat(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        buy_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        invalid_response = client.post("/api/v1/paper-portfolio/reset", json={"starting_balance": "0"})
        open_position_response = client.post(
            "/api/v1/paper-portfolio/reset",
            json={"starting_balance": "2500.00"},
        )
        sell_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "sell", "quantity": "1"},
        )
        reset_response = client.post(
            "/api/v1/paper-portfolio/reset",
            json={"starting_balance": "2500.00"},
        )
        snapshot_response = client.get("/api/v1/paper-portfolio")
        orders_response = client.get("/api/v1/execution/orders")
        fills_response = client.get("/api/v1/execution/fills")

    assert buy_response.status_code == 200
    assert buy_response.json()["accepted"] is True
    assert invalid_response.status_code == 422
    assert open_position_response.status_code == 409
    assert open_position_response.json()["error_code"] == "paper_portfolio_not_flat"
    assert sell_response.status_code == 200
    assert sell_response.json()["accepted"] is True

    assert reset_response.status_code == 200
    assert reset_response.json()["starting_balance"] == "2500.00000000"
    assert reset_response.json()["cash_balance"] == "2500.00000000"
    assert reset_response.json()["total_realized_pnl"] == "0"

    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["starting_balance"] == "2500.00000000"
    assert snapshot_response.json()["cash_balance"] == "2500.00000000"
    assert snapshot_response.json()["positions"] == []

    assert orders_response.status_code == 200
    assert len(orders_response.json()) == 2
    assert fills_response.status_code == 200
    assert len(fills_response.json()) == 2


def test_direct_market_orders_consume_daily_count_slots_and_block_next_request(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=2)
    import app.api.v1.endpoints.execution as execution_endpoint
    import app.api.v1.endpoints.execution_safety as safety_endpoint

    monkeypatch.setattr(execution_endpoint, "settings", settings)
    monkeypatch.setattr(safety_endpoint, "get_settings", lambda: settings)
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        buy_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        sell_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "sell", "quantity": "1"},
        )
        status_response = client.get("/api/v1/execution-safety/status")
        blocked_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        blocked_status_response = client.get("/api/v1/execution-safety/status")

    assert buy_response.status_code == 200
    assert buy_response.json()["accepted"] is True
    assert sell_response.status_code == 200
    assert sell_response.json()["accepted"] is True

    assert status_response.status_code == 200
    assert status_response.json()["current_daily_attempt_count"] == 2
    assert status_response.json()["remaining_daily_order_capacity"] == 0
    assert status_response.json()["blocking_reason"] == "max_daily_order_count_exceeded"

    assert blocked_response.status_code == 200
    assert blocked_response.json()["accepted"] is False
    assert blocked_response.json()["message"] == "max_daily_order_count_exceeded"
    assert blocked_response.json()["fill"] is None

    assert blocked_status_response.status_code == 200
    assert blocked_status_response.json()["current_daily_attempt_count"] == 2
    assert blocked_status_response.json()["remaining_daily_order_capacity"] == 0

    with db_session_factory() as session:
        attempts = ExecutionAttemptRepository(session).list_filtered(limit=10)
        assert [attempt.final_status for attempt in attempts] == ["blocked_by_safety", "filled", "filled"]
        assert attempts[0].final_reason == "max_daily_order_count_exceeded"


def test_direct_market_order_allows_risk_reducing_sell_after_daily_count_exhausted(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=1)
    import app.api.v1.endpoints.execution as execution_endpoint
    import app.api.v1.endpoints.execution_safety as safety_endpoint

    monkeypatch.setattr(execution_endpoint, "settings", settings)
    monkeypatch.setattr(safety_endpoint, "get_settings", lambda: settings)
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        buy_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        blocked_buy_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        sell_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "sell", "quantity": "1"},
        )
        oversell_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "sell", "quantity": "1"},
        )
        buy_status_response = client.get("/api/v1/execution-safety/status", params={"side": "buy"})
        sell_status_response = client.get("/api/v1/execution-safety/status", params={"side": "sell"})

    assert buy_response.status_code == 200
    assert buy_response.json()["accepted"] is True
    assert blocked_buy_response.status_code == 200
    assert blocked_buy_response.json()["accepted"] is False
    assert blocked_buy_response.json()["message"] == "max_daily_order_count_exceeded"
    assert sell_response.status_code == 200
    assert sell_response.json()["accepted"] is True
    assert sell_response.json()["updated_cash_balance"] == "9999.70000000"
    assert sell_response.json()["position"]["quantity"] == "0E-8"
    assert oversell_response.status_code == 200
    assert oversell_response.json()["accepted"] is False
    assert oversell_response.json()["message"] == "Insufficient position quantity for this sell order"

    assert buy_status_response.status_code == 200
    assert buy_status_response.json()["current_daily_attempt_count"] == 2
    assert buy_status_response.json()["remaining_daily_order_capacity"] == 0
    assert buy_status_response.json()["blocking_reason"] == "max_daily_order_count_exceeded"
    assert sell_status_response.status_code == 200
    assert sell_status_response.json()["current_daily_attempt_count"] == 2
    assert sell_status_response.json()["remaining_daily_order_capacity"] == 0
    assert sell_status_response.json()["blocking_reason"] is None
    assert sell_status_response.json()["metadata"]["risk_reducing_exits_allowed"] is True


def test_failed_direct_execution_leaves_no_counted_reservation(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=1)
    import app.api.v1.endpoints.execution as execution_endpoint
    import app.api.v1.endpoints.execution_safety as safety_endpoint

    monkeypatch.setattr(execution_endpoint, "settings", settings)
    monkeypatch.setattr(safety_endpoint, "get_settings", lambda: settings)
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        insufficient_cash_response = client.post(
            "/api/v1/execution/market-order",
            json={"symbol": "BTCUSDT", "side": "buy", "quantity": "1"},
        )
        status_response = client.get("/api/v1/execution-safety/status")

    assert insufficient_cash_response.status_code == 200
    assert insufficient_cash_response.json()["accepted"] is False
    assert insufficient_cash_response.json()["message"] == "insufficient_paper_cash"
    assert status_response.status_code == 200
    assert status_response.json()["current_daily_attempt_count"] == 0
    assert status_response.json()["remaining_daily_order_capacity"] == 1
