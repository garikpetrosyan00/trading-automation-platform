import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.execution_attempt import ExecutionAttempt
from app.core.errors import AppError
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.draft_balance import DraftBalanceService

ORDER_PUBLIC_FIELDS = {
    "id",
    "bot_id",
    "strategy_id",
    "symbol",
    "side",
    "order_type",
    "mode",
    "quantity",
    "requested_price",
    "requested_price_snapshot",
    "status",
    "decision_reason",
    "decision_metadata",
    "rejection_reason",
    "fill_count",
    "fills",
    "created_at",
    "updated_at",
}
ATTEMPT_PUBLIC_FIELDS = {
    "id",
    "bot_id",
    "strategy_id",
    "order_id",
    "symbol",
    "side",
    "mode",
    "broker",
    "requested_quantity",
    "requested_price",
    "decision_reason",
    "risk_status",
    "safety_status",
    "final_status",
    "final_reason",
    "metadata",
    "created_at",
}
PAPER_EQUITY_PUBLIC_FIELDS = {
    "id",
    "bot_id",
    "symbol",
    "quote_asset",
    "cash_available",
    "cash_locked",
    "base_quantity",
    "base_locked",
    "average_entry_price",
    "realized_pnl",
    "market_price",
    "position_value",
    "total_equity",
    "event_type",
    "created_at",
}


def _assets_by_symbol(payload: dict) -> dict[str, dict]:
    return {asset["asset"]: asset for asset in payload["assets"]}


def _assert_empty_paper_execution_reads(client: TestClient, bot_id: int) -> None:
    assert client.get(f"/api/v1/bots/{bot_id}/orders").json() == []
    assert client.get(f"/api/v1/bots/{bot_id}/execution-attempts").json() == []
    assert client.get(f"/api/v1/bots/{bot_id}/paper-equity").json() == {
        "bot_id": bot_id,
        "count": 0,
        "items": [],
    }
    assert client.get(f"/api/v1/execution-reconciliation-jobs").json() == []
    reconciliation = client.get(f"/api/v1/bots/{bot_id}/execution-reconciliation/status").json()
    assert reconciliation["unresolved_unknown_count"] == 0
    assert reconciliation["recovered_count"] == 0
    assert reconciliation["pending_delayed_reconciliation_count"] == 0
    assert reconciliation["claimed_delayed_reconciliation_count"] == 0
    assert reconciliation["exhausted_delayed_reconciliation_count"] == 0
    assert reconciliation["recent_attempts"] == []


def test_order_audit_lists_orders_after_paper_buy_and_sell_decisions(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
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


def test_manual_paper_buy_read_apis_are_consistent_and_allowlisted(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        run_response = client.post(f"/api/v1/bots/{bot.id}/run")
        orders_response = client.get(f"/api/v1/bots/{bot.id}/orders", params={"mode": "paper", "limit": 5})
        attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts", params={"mode": "paper", "limit": 5})
        draft_response = client.get(f"/api/v1/bots/{bot.id}/draft-balance")
        position_response = client.get(f"/api/v1/bots/{bot.id}/paper-position")
        equity_response = client.get(f"/api/v1/bots/{bot.id}/paper-equity", params={"limit": 5})
        activity_response = client.get(f"/api/v1/bots/{bot.id}/activity", params={"limit": 3})
        reconciliation_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")
        reconciliation_jobs_response = client.get("/api/v1/execution-reconciliation-jobs")

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "bought"
    assert run_response.json()["message"] == "buy_filled"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "buy_filled"

    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert len(orders) == 1
    assert set(orders[0]) == ORDER_PUBLIC_FIELDS
    assert orders[0]["bot_id"] == bot.id
    assert orders[0]["strategy_id"] == strategy.id
    assert orders[0]["symbol"] == "BTCUSDT"
    assert orders[0]["side"] == "buy"
    assert orders[0]["mode"] == "paper"
    assert orders[0]["status"] == "filled"
    assert orders[0]["fill_count"] == 1
    assert orders[0]["fills"] == []
    assert orders[0]["requested_price"] == "95.00000000"

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert len(attempts) == 1
    assert set(attempts[0]) == ATTEMPT_PUBLIC_FIELDS
    assert attempts[0]["bot_id"] == bot.id
    assert attempts[0]["strategy_id"] == strategy.id
    assert attempts[0]["order_id"] == orders[0]["id"]
    assert attempts[0]["symbol"] == "BTCUSDT"
    assert attempts[0]["side"] == "buy"
    assert attempts[0]["mode"] == "paper"
    assert attempts[0]["broker"] == "paper"
    assert attempts[0]["final_status"] == "filled"
    assert attempts[0]["final_reason"] == "Market buy order filled"
    assert attempts[0]["metadata"]["fill_id"] is not None

    assert draft_response.status_code == 200
    assets = _assets_by_symbol(draft_response.json())
    assert assets["USDT"] == {"asset": "USDT", "available": "9990.5", "locked": "0", "total": "9990.5"}
    assert assets["BTC"] == {"asset": "BTC", "available": "0.1", "locked": "0", "total": "0.1"}

    assert position_response.status_code == 200
    position = position_response.json()
    assert position["quantity"] == "0.1"
    assert position["average_entry_price"] == "95"
    assert position["realized_pnl"] == "0"

    assert equity_response.status_code == 200
    equity = equity_response.json()
    assert equity["bot_id"] == bot.id
    assert equity["count"] == 1
    assert len(equity["items"]) == 1
    assert set(equity["items"][0]) == PAPER_EQUITY_PUBLIC_FIELDS
    assert equity["items"][0]["event_type"] == "buy_fill"
    assert equity["items"][0]["base_quantity"] == "0.1"
    assert "source_order_id" not in equity_response.text
    assert "source_fill_id" not in equity_response.text

    assert activity_response.status_code == 200
    assert activity_response.json()["items"][0]["message"] == "buy_filled"
    assert activity_response.json()["items"][0]["side"] == "buy"
    assert reconciliation_response.status_code == 200
    assert reconciliation_response.json()["recent_attempts"] == []
    assert reconciliation_jobs_response.status_code == 200
    assert reconciliation_jobs_response.json() == []


def test_manual_paper_sell_read_apis_are_consistent_newest_first_and_allowlisted(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    strategy, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        buy_response = client.post(f"/api/v1/bots/{bot.id}/run")
        stub_market_data_service.set_price("BTCUSDT", "115")
        sell_response = client.post(f"/api/v1/bots/{bot.id}/run")
        orders_response = client.get(f"/api/v1/bots/{bot.id}/orders", params={"mode": "paper", "limit": 1})
        all_orders_response = client.get(f"/api/v1/bots/{bot.id}/orders", params={"mode": "paper", "limit": 5})
        attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts", params={"mode": "paper", "limit": 1})
        all_attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts", params={"mode": "paper", "limit": 5})
        draft_response = client.get(f"/api/v1/bots/{bot.id}/draft-balance")
        position_response = client.get(f"/api/v1/bots/{bot.id}/paper-position")
        equity_response = client.get(f"/api/v1/bots/{bot.id}/paper-equity", params={"limit": 5})
        reconciliation_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")
        reconciliation_jobs_response = client.get("/api/v1/execution-reconciliation-jobs")

    assert buy_response.status_code == 200
    assert buy_response.json()["message"] == "buy_filled"
    assert sell_response.status_code == 200
    assert sell_response.json()["action"] == "sold"
    assert sell_response.json()["message"] == "sell_filled"

    assert orders_response.status_code == 200
    latest_orders = orders_response.json()
    assert len(latest_orders) == 1
    assert latest_orders[0]["side"] == "sell"
    assert latest_orders[0]["status"] == "filled"
    assert latest_orders[0]["fill_count"] == 1
    assert set(latest_orders[0]) == ORDER_PUBLIC_FIELDS

    all_orders = all_orders_response.json()
    assert all_orders_response.status_code == 200
    assert [order["side"] for order in all_orders] == ["sell", "buy"]
    assert all(order["bot_id"] == bot.id and order["strategy_id"] == strategy.id for order in all_orders)

    assert attempts_response.status_code == 200
    latest_attempts = attempts_response.json()
    assert len(latest_attempts) == 1
    assert set(latest_attempts[0]) == ATTEMPT_PUBLIC_FIELDS
    assert latest_attempts[0]["side"] == "sell"
    assert latest_attempts[0]["order_id"] == latest_orders[0]["id"]
    assert latest_attempts[0]["final_status"] == "filled"
    assert latest_attempts[0]["final_reason"] == "Market sell order filled"

    all_attempts = all_attempts_response.json()
    assert all_attempts_response.status_code == 200
    assert [attempt["side"] for attempt in all_attempts] == ["sell", "buy"]
    assert all(attempt["final_status"] == "filled" for attempt in all_attempts)

    assets = _assets_by_symbol(draft_response.json())
    assert draft_response.status_code == 200
    assert assets["BTC"] == {"asset": "BTC", "available": "0", "locked": "0", "total": "0"}
    assert assets["USDT"] == {"asset": "USDT", "available": "10002", "locked": "0", "total": "10002"}

    assert position_response.status_code == 200
    position = position_response.json()
    assert position["quantity"] == "0"
    assert position["average_entry_price"] == "0"
    assert position["realized_pnl"] == "2"

    assert equity_response.status_code == 200
    equity = equity_response.json()
    assert equity["count"] == 2
    assert [item["event_type"] for item in equity["items"]] == ["sell_fill", "buy_fill"]
    assert set(equity["items"][0]) == PAPER_EQUITY_PUBLIC_FIELDS
    assert equity["items"][0]["base_quantity"] == "0"
    assert equity["items"][0]["cash_available"] == "10002"
    assert "source_order_id" not in equity_response.text
    assert "source_fill_id" not in equity_response.text

    assert reconciliation_response.status_code == 200
    assert reconciliation_response.json()["recent_attempts"] == []
    assert reconciliation_jobs_response.status_code == 200
    assert reconciliation_jobs_response.json() == []


def test_order_audit_retrieves_single_order_and_order_fills(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
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


def test_no_signal_manual_run_leaves_paper_read_apis_unchanged_except_activity(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "105")
        run_response = client.post(f"/api/v1/bots/{bot.id}/run")
        activity_response = client.get(f"/api/v1/bots/{bot.id}/activity", params={"limit": 3})
        draft_response = client.get(f"/api/v1/bots/{bot.id}/draft-balance")
        position_response = client.get(f"/api/v1/bots/{bot.id}/paper-position")
        _assert_empty_paper_execution_reads(client, bot.id)

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "no_action"
    assert run_response.json()["message"] == "evaluation_no_signal"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "evaluation_no_signal"

    assert activity_response.status_code == 200
    assert activity_response.json()["items"][0]["message"] == "evaluation_no_signal"

    assets = _assets_by_symbol(draft_response.json())
    assert draft_response.status_code == 200
    assert assets["USDT"] == {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"}
    assert assets["BTC"] == {"asset": "BTC", "available": "0", "locked": "0", "total": "0"}

    assert position_response.status_code == 200
    assert position_response.json()["quantity"] == "0"
    assert position_response.json()["realized_pnl"] == "0"

    assert PortfolioRepository(db_session).list_fills() == []
    assert PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot.id) == []


def test_rejected_manual_buy_read_apis_do_not_expose_false_filled_state(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    DraftBalanceService(DraftBalanceRepository(db_session), BotRepository(db_session)).reset_bot_draft_balance(
        bot.id,
        defaults={"USDT": (Decimal("1"), Decimal("0")), "BTC": (Decimal("0"), Decimal("0"))},
    )
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        run_response = client.post(f"/api/v1/bots/{bot.id}/run")
        orders_response = client.get(f"/api/v1/bots/{bot.id}/orders")
        attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts")
        draft_response = client.get(f"/api/v1/bots/{bot.id}/draft-balance")
        position_response = client.get(f"/api/v1/bots/{bot.id}/paper-position")
        equity_response = client.get(f"/api/v1/bots/{bot.id}/paper-equity")
        reconciliation_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "skipped"
    assert run_response.json()["message"] == "order_rejected"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "order_rejected"

    assert orders_response.status_code == 200
    assert orders_response.json() == []

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert len(attempts) == 1
    assert attempts[0]["side"] == "buy"
    assert attempts[0]["order_id"] is None
    assert attempts[0]["final_status"] == "rejected_by_broker"
    assert attempts[0]["final_reason"] == "insufficient_draft_balance_available"
    assert attempts[0]["metadata"]["fill_id"] is None

    assert draft_response.status_code == 200
    assert draft_response.json() == {
        "bot_id": bot.id,
        "assets": [
            {"asset": "BTC", "available": "0", "locked": "0", "total": "0"},
            {"asset": "USDT", "available": "1", "locked": "0", "total": "1"},
        ],
    }
    assert position_response.status_code == 200
    assert position_response.json()["quantity"] == "0"
    assert equity_response.status_code == 200
    assert equity_response.json() == {"bot_id": bot.id, "count": 0, "items": []}
    assert reconciliation_response.status_code == 200
    assert reconciliation_response.json()["recent_attempts"] == []
    assert PortfolioRepository(db_session).list_fills() == []


def test_rejected_manual_sell_read_apis_do_not_expose_false_filled_state(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
    monkeypatch,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        buy_response = client.post(f"/api/v1/bots/{bot.id}/run")
        assert buy_response.json()["message"] == "buy_filled"

    def fail_sell_settlement(self, **kwargs):
        raise AppError("forced sell settlement failure", status_code=409, error_code="forced_sell_settlement_failure")

    monkeypatch.setattr(DraftBalanceService, "apply_draft_balance_sell_fill", fail_sell_settlement)

    with TestClient(app) as client:
        stub_market_data_service.set_price("BTCUSDT", "115")
        run_response = client.post(f"/api/v1/bots/{bot.id}/run")
        orders_response = client.get(f"/api/v1/bots/{bot.id}/orders")
        attempts_response = client.get(f"/api/v1/bots/{bot.id}/execution-attempts")
        draft_response = client.get(f"/api/v1/bots/{bot.id}/draft-balance")
        position_response = client.get(f"/api/v1/bots/{bot.id}/paper-position")
        equity_response = client.get(f"/api/v1/bots/{bot.id}/paper-equity")
        reconciliation_response = client.get(f"/api/v1/bots/{bot.id}/execution-reconciliation/status")

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "skipped"
    assert run_response.json()["message"] == "order_rejected"

    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert [order["side"] for order in orders] == ["sell", "buy"]
    assert [order["status"] for order in orders] == ["rejected", "filled"]
    assert orders[0]["fill_count"] == 0
    assert orders[0]["rejection_reason"] == "forced_sell_settlement_failure"
    assert orders[1]["fill_count"] == 1

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert [attempt["side"] for attempt in attempts] == ["sell", "buy"]
    assert attempts[0]["order_id"] == orders[0]["id"]
    assert attempts[0]["final_status"] == "rejected_by_broker"
    assert attempts[0]["final_reason"] == "forced_sell_settlement_failure"
    assert attempts[0]["metadata"]["fill_id"] is None
    assert attempts[1]["order_id"] == orders[1]["id"]
    assert attempts[1]["final_status"] == "filled"

    assets = _assets_by_symbol(draft_response.json())
    assert draft_response.status_code == 200
    assert assets["BTC"] == {"asset": "BTC", "available": "0.1", "locked": "0", "total": "0.1"}
    assert assets["USDT"] == {"asset": "USDT", "available": "9990.5", "locked": "0", "total": "9990.5"}
    assert position_response.status_code == 200
    assert position_response.json()["quantity"] == "0.1"
    assert equity_response.status_code == 200
    assert [item["event_type"] for item in equity_response.json()["items"]] == ["buy_fill"]
    assert reconciliation_response.status_code == 200
    assert reconciliation_response.json()["recent_attempts"] == []
    fills = PortfolioRepository(db_session).list_fills()
    assert len(fills) == 1
    assert fills[0].side == "buy"


def test_bot_scoped_read_apis_are_isolated_between_bots(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, selected_bot, _ = bot_stack_factory(db_session, name="Selected API Bot")
    _, other_bot, _ = bot_stack_factory(db_session, name="Other API Bot")
    reset_draft_balance_for_bot(db_session, selected_bot.id)
    reset_draft_balance_for_bot(db_session, other_bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{other_bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        other_run_response = client.post(f"/api/v1/bots/{other_bot.id}/run")
        selected_orders = client.get(f"/api/v1/bots/{selected_bot.id}/orders")
        selected_attempts = client.get(f"/api/v1/bots/{selected_bot.id}/execution-attempts")
        selected_draft = client.get(f"/api/v1/bots/{selected_bot.id}/draft-balance")
        selected_position = client.get(f"/api/v1/bots/{selected_bot.id}/paper-position")
        selected_equity = client.get(f"/api/v1/bots/{selected_bot.id}/paper-equity")
        other_orders = client.get(f"/api/v1/bots/{other_bot.id}/orders")
        other_attempts = client.get(f"/api/v1/bots/{other_bot.id}/execution-attempts")
        other_equity = client.get(f"/api/v1/bots/{other_bot.id}/paper-equity")

    assert other_run_response.status_code == 200
    assert other_run_response.json()["message"] == "buy_filled"

    assert selected_orders.status_code == 200
    assert selected_orders.json() == []
    assert selected_attempts.status_code == 200
    assert selected_attempts.json() == []
    assert selected_equity.status_code == 200
    assert selected_equity.json() == {"bot_id": selected_bot.id, "count": 0, "items": []}
    assert selected_position.status_code == 200
    assert selected_position.json()["quantity"] == "0"
    selected_assets = _assets_by_symbol(selected_draft.json())
    assert selected_assets["USDT"] == {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"}
    assert selected_assets["BTC"] == {"asset": "BTC", "available": "0", "locked": "0", "total": "0"}

    assert other_orders.status_code == 200
    assert len(other_orders.json()) == 1
    assert other_orders.json()[0]["bot_id"] == other_bot.id
    assert other_attempts.status_code == 200
    assert len(other_attempts.json()) == 1
    assert other_attempts.json()[0]["bot_id"] == other_bot.id
    assert other_equity.status_code == 200
    assert other_equity.json()["count"] == 1
    assert other_equity.json()["items"][0]["bot_id"] == other_bot.id


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
        missing_bot_orders_response = client.get("/api/v1/bots/999999/orders")
        missing_bot_attempts_response = client.get("/api/v1/bots/999999/execution-attempts")
        too_large_limit_response = client.get("/api/v1/orders", params={"limit": 101})
        too_large_attempt_limit_response = client.get("/api/v1/execution-attempts", params={"limit": 101})
        invalid_filter_response = client.get("/api/v1/orders", params={"side": "hold"})
        invalid_attempt_filter_response = client.get("/api/v1/execution-attempts", params={"final_status": "nope"})

    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "order_not_found"
    assert missing_attempt_response.status_code == 404
    assert missing_attempt_response.json()["error_code"] == "execution_attempt_not_found"
    assert missing_bot_orders_response.status_code == 200
    assert missing_bot_orders_response.json() == []
    assert missing_bot_attempts_response.status_code == 200
    assert missing_bot_attempts_response.json() == []
    assert too_large_limit_response.status_code == 422
    assert too_large_attempt_limit_response.status_code == 422
    assert invalid_filter_response.status_code == 422
    assert invalid_attempt_filter_response.status_code == 422
