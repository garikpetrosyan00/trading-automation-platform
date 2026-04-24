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
        "starting_cash": "1000.00000000",
        "cash_balance": "1000.00000000",
        "market_value": "0",
        "equity": "1000.00000000",
        "unrealized_pnl": "0",
        "realized_pnl": "0",
    }

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
        "updated_cash_balance": "499.24975000",
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
        "updated_cash_balance": "702.94385200",
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
