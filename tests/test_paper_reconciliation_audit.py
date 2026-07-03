import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.bot_run import BotRun
from app.models.draft_balance import DraftBalance
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_equity_snapshot import PaperEquitySnapshot
from app.models.paper_position import PaperPosition
from app.models.run_event import RunEvent
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.paper_reconciliation_audit import ISSUE_DESCRIPTIONS


AUDIT_PUBLIC_FIELDS = {
    "bot_id",
    "ok",
    "issues",
    "checked_attempt_count",
    "checked_order_count",
    "checked_fill_count",
    "checked_run_event_count",
    "checked_equity_snapshot_count",
    "read_only",
}
ISSUE_PUBLIC_FIELDS = {
    "code",
    "description",
    "severity",
    "symbol",
    "side",
    "artifact",
}
ISSUE_CODE_ALLOWLIST = set(ISSUE_DESCRIPTIONS)


def test_paper_reconciliation_audit_missing_bot_returns_stable_not_found(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/bots/999999/paper-reconciliation/audit")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_paper_reconciliation_audit_clean_successful_buy_returns_ok(
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
        stub_market_data_service.set_price("BTCUSDT", "95")
        assert client.post(f"/api/v1/bots/{bot.id}/run").json()["action"] == "bought"
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert body["bot_id"] == bot.id
    assert body["ok"] is True
    assert body["issues"] == []
    assert body["checked_attempt_count"] == 1
    assert body["checked_order_count"] == 1
    assert body["checked_fill_count"] == 1
    assert body["checked_equity_snapshot_count"] == 1
    assert body["read_only"] is True


def test_paper_reconciliation_audit_clean_successful_sell_returns_ok(
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
        stub_market_data_service.set_price("BTCUSDT", "95")
        assert client.post(f"/api/v1/bots/{bot.id}/run").json()["action"] == "bought"
        stub_market_data_service.set_price("BTCUSDT", "115")
        assert client.post(f"/api/v1/bots/{bot.id}/run").json()["action"] == "sold"
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert body["ok"] is True
    assert body["issues"] == []
    assert body["checked_attempt_count"] == 2
    assert body["checked_order_count"] == 2
    assert body["checked_fill_count"] == 2
    assert body["checked_equity_snapshot_count"] == 2


def test_paper_reconciliation_audit_clean_rejected_gate_returns_ok(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
    noop_bot_runner,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = _build_disabled_runner(db_session_factory, stub_market_data_service)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")
    asyncio.run(runner.run_bot_once(bot.id))
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert body["ok"] is True
    assert body["issues"] == []
    assert body["checked_attempt_count"] == 1
    assert body["checked_order_count"] == 0
    assert body["checked_fill_count"] == 0
    assert body["checked_equity_snapshot_count"] == 0


def test_paper_reconciliation_audit_flags_missing_fill(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    reset_draft_balance_for_bot,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_draft_balance_for_bot(db_session, bot.id)
    order = _add_order(db_session, bot_id=bot.id, status="filled", side="buy")
    _add_attempt(db_session, bot_id=bot.id, order_id=order.id, final_status="filled", side="buy")
    _add_paper_position(db_session, bot_id=bot.id)
    _add_snapshot(db_session, bot_id=bot.id, order_id=order.id, fill_id=None, event_type="buy_fill")
    _add_run_event(db_session, bot_id=bot.id, message="order_filled", payload={"side": "buy", "symbol": "BTCUSDT"})
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert body["ok"] is False
    assert _issue_codes(body) <= ISSUE_CODE_ALLOWLIST
    assert "filled_order_missing_fill" in _issue_codes(body)


def test_paper_reconciliation_audit_flags_rejected_attempt_with_side_effect_order(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    order = _add_order(db_session, bot_id=bot.id, status="rejected", side="buy")
    _add_attempt(
        db_session,
        bot_id=bot.id,
        order_id=order.id,
        final_status="rejected_by_broker",
        final_reason="paper_trading_disabled",
        side="buy",
    )
    _add_run_event(
        db_session,
        bot_id=bot.id,
        message="order_rejected",
        payload={"side": "buy", "symbol": "BTCUSDT", "message": "paper_trading_disabled"},
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert body["ok"] is False
    assert _issue_codes(body) <= ISSUE_CODE_ALLOWLIST
    assert "rejected_attempt_has_order" in _issue_codes(body)


def test_paper_reconciliation_audit_response_fields_are_public_and_allowlisted(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    _add_attempt(
        db_session,
        bot_id=bot.id,
        order_id=None,
        final_status="rejected_by_broker",
        final_reason="paper_trading_disabled",
        side="buy",
        metadata={"secret": "unsafe", "fill_id": None},
    )
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == AUDIT_PUBLIC_FIELDS
    assert all(set(issue) == ISSUE_PUBLIC_FIELDS for issue in body["issues"])
    assert body["read_only"] is True
    assert _issue_codes(body) <= ISSUE_CODE_ALLOWLIST
    serialized = response.text
    assert "metadata" not in serialized
    assert "secret" not in serialized
    assert "unsafe" not in serialized
    assert "attempt_id" not in serialized
    assert "order_id" not in serialized
    assert "fill_id" not in serialized


def test_paper_reconciliation_audit_is_read_only(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    reset_draft_balance_for_bot,
    noop_bot_runner,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance_for_bot(db_session, bot.id)
    runner = bot_runner_factory()
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=runner)

    with TestClient(app) as client:
        assert client.post(f"/api/v1/bots/{bot.id}/start").status_code == 200
        stub_market_data_service.set_price("BTCUSDT", "95")
        assert client.post(f"/api/v1/bots/{bot.id}/run").json()["action"] == "bought"

    before = _artifact_summary(db_session, bot.id)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    with TestClient(app) as client:
        first_response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")
        second_response = client.get(f"/api/v1/bots/{bot.id}/paper-reconciliation/audit")
    after = _artifact_summary(db_session, bot.id)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert first_response.json()["ok"] is True
    assert first_response.json()["read_only"] is True
    assert after == before


def test_paper_reconciliation_audit_issue_codes_are_explicitly_allowlisted() -> None:
    expected_codes = {
        "filled_attempt_missing_order",
        "filled_order_missing_fill",
        "filled_attempt_missing_equity_snapshot",
        "filled_buy_missing_draft_balance",
        "filled_buy_missing_paper_position",
        "filled_sell_missing_draft_balance",
        "filled_sell_missing_paper_position",
        "rejected_attempt_has_order",
        "rejected_attempt_has_fill",
        "rejected_attempt_has_filled_attempt",
        "rejected_attempt_has_equity_snapshot",
        "duplicate_filled_attempt_for_order",
        "run_event_missing_for_filled_attempt",
        "run_event_missing_for_rejected_attempt",
    }

    assert ISSUE_CODE_ALLOWLIST == expected_codes


def _build_disabled_runner(db_session_factory, stub_market_data_service):
    from app.engine.bot_runner import BotRunner, RunnerConfig

    return BotRunner(
        session_factory=db_session_factory,
        market_data_service=stub_market_data_service,
        config=RunnerConfig(
            enabled=True,
            poll_interval_seconds=3600,
            simulation_enabled=True,
            simulation_fee_bps=Decimal("0"),
            simulation_slippage_bps=Decimal("0"),
            paper_trading_enabled=False,
        ),
    )


def _issue_codes(body: dict) -> set[str]:
    return {issue["code"] for issue in body["issues"]}


def _add_order(db_session, *, bot_id: int, status: str, side: str) -> SimulatedOrder:
    order = SimulatedOrder(
        bot_id=bot_id,
        strategy_id=None,
        symbol="BTCUSDT",
        side=side,
        order_type="market",
        quantity=Decimal("0.1"),
        requested_price_snapshot=Decimal("95"),
        status=status,
        mode="paper",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def _add_attempt(
    db_session,
    *,
    bot_id: int,
    order_id: int | None,
    final_status: str,
    side: str,
    final_reason: str = "Market buy order filled",
    metadata: dict | None = None,
) -> ExecutionAttempt:
    attempt = ExecutionAttempt(
        bot_id=bot_id,
        strategy_id=None,
        order_id=order_id,
        symbol="BTCUSDT",
        side=side,
        mode="paper",
        broker="paper",
        requested_quantity=Decimal("0.1"),
        requested_price=Decimal("95"),
        risk_status="allowed",
        safety_status="allowed" if final_status == "filled" else final_reason,
        final_status=final_status,
        final_reason=final_reason,
        metadata_=metadata,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


def _add_paper_position(db_session, *, bot_id: int) -> None:
    db_session.add(
        PaperPosition(
            bot_id=bot_id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.1"),
            average_entry_price=Decimal("95"),
            realized_pnl=Decimal("0"),
        )
    )
    db_session.commit()


def _add_snapshot(
    db_session,
    *,
    bot_id: int,
    order_id: int,
    fill_id: int | None,
    event_type: str,
) -> None:
    db_session.add(
        PaperEquitySnapshot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            quote_asset="USDT",
            cash_available=Decimal("990.5"),
            cash_locked=Decimal("0"),
            base_quantity=Decimal("0.1"),
            base_locked=Decimal("0"),
            average_entry_price=Decimal("95"),
            realized_pnl=Decimal("0"),
            market_price=Decimal("95"),
            position_value=Decimal("9.5"),
            total_equity=Decimal("1000"),
            event_type=event_type,
            source_order_id=order_id,
            source_fill_id=fill_id,
        )
    )
    db_session.commit()


def _add_run_event(db_session, *, bot_id: int, message: str, payload: dict) -> None:
    bot_run = BotRun(
        bot_id=bot_id,
        trigger_type="manual",
        status="running",
        summary="test run",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(bot_run)
    db_session.flush()
    db_session.add(
        RunEvent(
            bot_run_id=bot_run.id,
            event_type="system",
            level="info",
            message=message,
            payload=payload,
        )
    )
    db_session.commit()


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
        "paper_position": _position_tuple(
            PaperPositionRepository(db_session).get_for_bot_symbol(bot_id=bot_id, symbol="BTCUSDT")
        ),
        "snapshots": [
            (snapshot.id, snapshot.event_type, snapshot.source_order_id, snapshot.source_fill_id)
            for snapshot in PaperEquitySnapshotRepository(db_session).list_latest_for_bot(bot_id=bot_id, limit=100)
        ],
        "run_events": [(event.id, event.message) for event in RunEventRepository(db_session).list_for_bot(bot_id)],
        "draft_balance_rows": db_session.query(DraftBalance).count(),
        "position_rows": db_session.query(PaperPosition).count(),
        "snapshot_rows": db_session.query(PaperEquitySnapshot).count(),
        "order_rows": db_session.query(SimulatedOrder).count(),
        "fill_rows": db_session.query(SimulatedFill).count(),
        "attempt_rows": db_session.query(ExecutionAttempt).count(),
    }


def _position_tuple(position):
    if position is None:
        return None
    return (
        position.symbol,
        position.quantity,
        position.average_entry_price,
        position.realized_pnl,
    )
