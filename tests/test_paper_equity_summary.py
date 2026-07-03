import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository


SUMMARY_FIELDS = {
    "bot_id",
    "mode",
    "status",
    "paper_trading_enabled",
    "starting_cash",
    "current_cash",
    "open_position_count",
    "open_positions_value",
    "latest_total_equity",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "equity_snapshot_count",
    "latest_snapshot",
    "read_only",
}
SNAPSHOT_FIELDS = {
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


def test_paper_equity_summary_empty_new_bot_returns_safe_zero_state(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")

    assert response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    assert body == {
        "bot_id": bot.id,
        "mode": "paper",
        "status": "draft",
        "paper_trading_enabled": True,
        "starting_cash": "0",
        "current_cash": "0",
        "open_position_count": 0,
        "open_positions_value": "0",
        "latest_total_equity": None,
        "realized_pnl": "0",
        "unrealized_pnl": "0",
        "total_pnl": "0",
        "equity_snapshot_count": 0,
        "latest_snapshot": None,
        "read_only": True,
    }


def test_paper_equity_summary_after_buy_reports_public_equity_state(
    db_session,
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    _run_bot_once(
        db_session_factory,
        stub_market_data_service,
        bot_id=bot.id,
        price="95",
        expected_action="bought",
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")
        overview_response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

    assert response.status_code == 200
    assert overview_response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    assert body["status"] == "active"
    assert body["starting_cash"] == "10000"
    assert body["current_cash"] == "9990.5"
    assert body["open_position_count"] == 1
    assert body["open_positions_value"] == "9.5"
    assert body["latest_total_equity"] == "10000"
    assert body["realized_pnl"] == "0"
    assert body["unrealized_pnl"] == "0"
    assert body["total_pnl"] == "0"
    assert body["equity_snapshot_count"] == 1
    assert body["latest_snapshot"] == overview_response.json()["latest_equity_snapshot"]
    assert body["latest_snapshot"]["event_type"] == "buy_fill"
    assert body["read_only"] is True


def test_paper_equity_summary_after_sell_reports_closed_position_and_pnl(
    db_session,
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    _run_bot_once(
        db_session_factory,
        stub_market_data_service,
        bot_id=bot.id,
        price="95",
        expected_action="bought",
    )
    _run_bot_once(
        db_session_factory,
        stub_market_data_service,
        bot_id=bot.id,
        price="115",
        expected_action="sold",
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")

    assert response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    assert body["current_cash"] == "10002"
    assert body["open_position_count"] == 0
    assert body["open_positions_value"] == "0"
    assert body["latest_total_equity"] == "10002"
    assert body["realized_pnl"] == "2"
    assert body["unrealized_pnl"] == "0"
    assert body["total_pnl"] == "2"
    assert body["starting_cash"] == "10000"
    assert body["equity_snapshot_count"] == 2
    assert body["latest_snapshot"]["event_type"] == "sell_fill"
    assert body["latest_snapshot"]["base_quantity"] == "0"


def test_paper_equity_summary_reports_disabled_paper_trading_flag(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    import app.api.v1.endpoints.paper_equity as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: Settings(PAPER_TRADING_ENABLED=False))
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")

    assert response.status_code == 200
    assert response.json()["paper_trading_enabled"] is False


def test_paper_equity_summary_missing_bot_returns_stable_not_found(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/bots/999999/paper/equity-summary")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_paper_equity_summary_repeated_calls_are_read_only(
    db_session,
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    _run_bot_once(
        db_session_factory,
        stub_market_data_service,
        bot_id=bot.id,
        price="95",
        expected_action="bought",
    )
    before = _artifact_summary(db_session, bot.id)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        first = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")
        second = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")
    after = _artifact_summary(db_session, bot.id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["read_only"] is True
    assert after == before


def test_paper_equity_summary_does_not_expose_unsafe_internal_metadata(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    db_session.add(
        ExecutionAttempt(
            bot_id=bot.id,
            strategy_id=bot.strategy_id,
            order_id=None,
            symbol="BTCUSDT",
            side="buy",
            mode="paper",
            broker="paper",
            requested_quantity=Decimal("0.1"),
            requested_price=Decimal("95"),
            risk_status="allowed",
            safety_status="paper_trading_disabled",
            final_status="rejected_by_broker",
            final_reason="paper_trading_disabled",
            metadata_={"secret": "unsafe", "raw_payload": {"token": "hidden"}},
        )
    )
    db_session.commit()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/equity-summary")

    assert response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    _assert_no_unsafe_internal_metadata(body)
    serialized = response.text
    assert "metadata" not in serialized
    assert "secret" not in serialized
    assert "unsafe" not in serialized
    assert "raw_payload" not in serialized
    assert "token" not in serialized
    assert "order_id" not in serialized
    assert "fill_id" not in serialized
    assert "attempt_id" not in serialized


def _run_bot_once(db_session_factory, stub_market_data_service, *, bot_id: int, price: str, expected_action: str) -> None:
    from app.engine.bot_runner import BotRunner, RunnerConfig

    runner = BotRunner(
        session_factory=db_session_factory,
        market_data_service=stub_market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=3600,
            simulation_enabled=True,
            simulation_fee_bps=Decimal("0"),
            simulation_slippage_bps=Decimal("0"),
        ),
    )
    runner.start_bot(bot_id)
    stub_market_data_service.set_price("BTCUSDT", price)
    response = asyncio.run(runner.run_bot_once(bot_id))
    assert response.action == expected_action


def _assert_public_shape(body: dict) -> None:
    assert set(body) == SUMMARY_FIELDS
    if body["latest_snapshot"] is not None:
        assert set(body["latest_snapshot"]) == SNAPSHOT_FIELDS


def _assert_no_unsafe_internal_metadata(value) -> None:
    forbidden = {
        "metadata",
        "secret",
        "raw_payload",
        "token",
        "order_id",
        "fill_id",
        "attempt_id",
        "client_order_id",
        "source_order_id",
        "source_fill_id",
        "stack",
        "traceback",
    }
    if isinstance(value, dict):
        for key, nested_value in value.items():
            assert key not in forbidden
            if isinstance(nested_value, str):
                assert nested_value not in forbidden
            _assert_no_unsafe_internal_metadata(nested_value)
    elif isinstance(value, list):
        for item in value:
            _assert_no_unsafe_internal_metadata(item)


def _artifact_summary(db_session, bot_id: int) -> dict[str, object]:
    return {
        "orders": [
            (order.id, order.status, order.side)
            for order in PortfolioRepository(db_session).list_orders_filtered(bot_id=bot_id, mode="paper", limit=100)
        ],
        "fills": [(fill.id, fill.order_id, fill.side) for fill in PortfolioRepository(db_session).list_fills()],
        "attempts": [
            (attempt.id, attempt.final_status, attempt.final_reason)
            for attempt in ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot_id, mode="paper", limit=100)
        ],
        "draft_balances": [
            (row.asset, row.available, row.locked) for row in DraftBalanceRepository(db_session).list_for_bot(bot_id)
        ],
        "paper_positions": [
            (row.symbol, row.quantity, row.average_entry_price, row.realized_pnl)
            for row in PaperPositionRepository(db_session).list_for_bot(bot_id=bot_id)
        ],
        "snapshots": [
            (snapshot.id, snapshot.event_type)
            for snapshot in PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot_id, limit=100)
        ],
    }
