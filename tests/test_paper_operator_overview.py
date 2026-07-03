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


OVERVIEW_FIELDS = {
    "bot_id",
    "mode",
    "status",
    "paper_trading_enabled",
    "draft_balance",
    "paper_positions",
    "latest_equity_snapshot",
    "recent_execution_summary",
    "latest_reconciliation_audit",
    "read_only",
}
DRAFT_BALANCE_FIELDS = {"assets"}
DRAFT_ASSET_FIELDS = {"asset", "available", "locked", "total"}
POSITION_FIELDS = {
    "symbol",
    "base_asset",
    "quote_asset",
    "quantity",
    "average_entry_price",
    "realized_pnl",
    "updated_at",
}
EQUITY_FIELDS = {
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
EXECUTION_SUMMARY_FIELDS = {
    "recent_attempt_count",
    "filled_attempt_count",
    "rejected_attempt_count",
    "latest_attempt_status",
    "latest_attempt_reason",
    "latest_run_event_message",
}
AUDIT_FIELDS = {
    "ok",
    "issue_count",
    "issues",
    "checked_attempt_count",
    "checked_order_count",
    "checked_fill_count",
    "checked_run_event_count",
    "checked_equity_snapshot_count",
    "read_only",
}
ISSUE_FIELDS = {"code", "description", "severity", "symbol", "side", "artifact"}


def test_paper_operator_overview_empty_new_bot_returns_safe_empty_state(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == OVERVIEW_FIELDS
    _assert_public_shape(body)
    assert body["bot_id"] == bot.id
    assert body["mode"] == "paper"
    assert body["status"] == "draft"
    assert body["paper_trading_enabled"] is True
    assert body["draft_balance"] == {"assets": []}
    assert body["paper_positions"] == []
    assert body["latest_equity_snapshot"] is None
    assert body["recent_execution_summary"] == {
        "recent_attempt_count": 0,
        "filled_attempt_count": 0,
        "rejected_attempt_count": 0,
        "latest_attempt_status": None,
        "latest_attempt_reason": None,
        "latest_run_event_message": None,
    }
    assert body["latest_reconciliation_audit"]["ok"] is True
    assert body["latest_reconciliation_audit"]["issue_count"] == 0
    assert body["latest_reconciliation_audit"]["read_only"] is True
    assert body["read_only"] is True


def test_paper_operator_overview_after_buy_shows_public_state_and_clean_audit(
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
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")
        audit_response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    assert audit_response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    assert body["status"] == "active"
    assert _assets_by_symbol(body["draft_balance"])["BTC"]["available"] == "0.1"
    assert len(body["paper_positions"]) == 1
    assert body["paper_positions"][0]["symbol"] == "BTCUSDT"
    assert body["paper_positions"][0]["quantity"] == "0.1"
    assert body["latest_equity_snapshot"]["event_type"] == "buy_fill"
    assert body["latest_equity_snapshot"]["base_quantity"] == "0.1"
    assert body["recent_execution_summary"]["recent_attempt_count"] == 1
    assert body["recent_execution_summary"]["filled_attempt_count"] == 1
    assert body["recent_execution_summary"]["latest_attempt_status"] == "filled"
    assert body["latest_reconciliation_audit"]["ok"] is True
    assert body["latest_reconciliation_audit"]["issues"] == []
    assert body["latest_reconciliation_audit"] == _overview_audit_from_dedicated_response(audit_response.json())
    assert body["read_only"] is True


def test_paper_operator_overview_after_sell_shows_updated_public_state_and_clean_audit(
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
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

    assert response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    assert _assets_by_symbol(body["draft_balance"])["BTC"]["available"] == "0"
    assert body["paper_positions"][0]["quantity"] == "0"
    assert body["latest_equity_snapshot"]["event_type"] == "sell_fill"
    assert body["latest_equity_snapshot"]["base_quantity"] == "0"
    assert body["recent_execution_summary"]["recent_attempt_count"] == 2
    assert body["recent_execution_summary"]["filled_attempt_count"] == 2
    assert body["recent_execution_summary"]["latest_attempt_status"] == "filled"
    assert body["latest_reconciliation_audit"]["ok"] is True


def test_paper_operator_overview_reports_disabled_paper_trading_flag(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    import app.api.v1.endpoints.paper_operator as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: Settings(PAPER_TRADING_ENABLED=False))
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

    assert response.status_code == 200
    assert response.json()["paper_trading_enabled"] is False


def test_paper_operator_overview_does_not_expose_live_or_testnet_safety_flags(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    import app.api.v1.endpoints.paper_operator as endpoint

    monkeypatch.setattr(
        endpoint,
        "get_settings",
        lambda: Settings(
            EXECUTION_LIVE_ENABLED=True,
            BINANCE_TESTNET_BROKER_ENABLED=True,
            BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=True,
            BINANCE_TESTNET_DRY_RUN_ENABLED=True,
            BINANCE_TESTNET_API_KEY="test-key",
            BINANCE_TESTNET_API_SECRET="test-secret",
        ),
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

    assert response.status_code == 200
    body = response.json()
    _assert_public_shape(body)
    _assert_no_unsafe_internal_metadata(body)
    serialized = response.text
    assert "live_execution_enabled" not in serialized
    assert "binance_testnet" not in serialized
    assert "dry_run" not in serialized
    assert "test-key" not in serialized
    assert "test-secret" not in serialized


def test_paper_operator_overview_missing_bot_returns_stable_not_found(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/bots/999999/paper/operator-overview")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_paper_operator_overview_draft_paused_and_no_signal_do_not_look_filled(
    db_session,
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    _, draft_bot, _ = bot_stack_factory(db_session, name="Draft overview bot")
    _, paused_bot, _ = bot_stack_factory(db_session, name="Paused overview bot", status="paused")
    funded_account(db_session)
    _, no_signal_bot, _ = bot_stack_factory(db_session, name="No signal overview bot")
    reset_draft_balance_for_bot(db_session, no_signal_bot.id)
    _run_bot_once(
        db_session_factory,
        stub_market_data_service,
        bot_id=no_signal_bot.id,
        price="105",
        expected_action="no_action",
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        draft_response = client.get(f"/api/v1/bots/{draft_bot.id}/paper/operator-overview")
        paused_response = client.get(f"/api/v1/bots/{paused_bot.id}/paper/operator-overview")
        no_signal_response = client.get(f"/api/v1/bots/{no_signal_bot.id}/paper/operator-overview")

    for response in (draft_response, paused_response, no_signal_response):
        assert response.status_code == 200
        body = response.json()
        _assert_public_shape(body)
        assert body["recent_execution_summary"]["filled_attempt_count"] == 0
        assert body["recent_execution_summary"]["latest_attempt_status"] is None
        assert body["latest_equity_snapshot"] is None
        assert "order_filled" not in response.text
        assert "buy_fill" not in response.text
        assert "sell_fill" not in response.text
    assert draft_response.json()["status"] == "draft"
    assert paused_response.json()["status"] == "paused"
    assert no_signal_response.json()["recent_execution_summary"]["latest_run_event_message"] == "evaluation_no_signal"


def test_paper_operator_overview_repeated_calls_are_read_only(
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
        first = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")
        second = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")
    after = _artifact_summary(db_session, bot.id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["read_only"] is True
    assert after == before


def test_paper_operator_overview_does_not_expose_unsafe_internal_metadata(
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
        response = client.get(f"/api/v1/bots/{bot.id}/paper/operator-overview")

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


def _assets_by_symbol(draft_balance: dict) -> dict[str, dict]:
    return {asset["asset"]: asset for asset in draft_balance["assets"]}


def _assert_public_shape(body: dict) -> None:
    assert set(body) == OVERVIEW_FIELDS
    assert set(body["draft_balance"]) == DRAFT_BALANCE_FIELDS
    assert all(set(asset) == DRAFT_ASSET_FIELDS for asset in body["draft_balance"]["assets"])
    assert all(set(position) == POSITION_FIELDS for position in body["paper_positions"])
    if body["latest_equity_snapshot"] is not None:
        assert set(body["latest_equity_snapshot"]) == EQUITY_FIELDS
    assert set(body["recent_execution_summary"]) == EXECUTION_SUMMARY_FIELDS
    assert set(body["latest_reconciliation_audit"]) == AUDIT_FIELDS
    assert all(set(issue) == ISSUE_FIELDS for issue in body["latest_reconciliation_audit"]["issues"])


def _overview_audit_from_dedicated_response(audit: dict) -> dict:
    payload = dict(audit)
    payload.pop("bot_id")
    payload["issue_count"] = len(payload["issues"])
    return payload


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
