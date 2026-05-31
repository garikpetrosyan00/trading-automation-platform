from app.main import app


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
