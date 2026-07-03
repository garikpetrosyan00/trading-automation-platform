from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_accounting_event import PaperAccountingEvent
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.execution_safety_status import ExecutionSafetyStatusService


EXECUTION_SAFETY_STATUS_PUBLIC_FIELDS = {
    "global_execution_enabled",
    "live_execution_enabled",
    "paper_trading_enabled",
    "paper_execution_allowed",
    "binance_testnet_broker_enabled",
    "binance_testnet_order_submission_enabled",
    "binance_testnet_credentials_configured",
    "binance_testnet_dry_run_enabled",
    "max_order_notional",
    "max_daily_order_count",
    "max_daily_loss",
    "utc_day_start",
    "current_daily_attempt_count",
    "remaining_daily_order_capacity",
    "current_daily_realized_pnl",
    "current_daily_realized_loss",
    "remaining_daily_loss_capacity",
    "is_daily_loss_limit_exceeded",
    "is_execution_currently_allowed",
    "blocking_reason",
    "metadata",
}


def add_execution_attempt(
    session,
    *,
    bot_id: int | None,
    created_at: datetime | None = None,
    final_status: str = "filled",
) -> None:
    session.add(
        ExecutionAttempt(
            bot_id=bot_id,
            strategy_id=None,
            symbol="BTCUSDT",
            side="buy",
            mode="paper",
            broker="paper",
            requested_quantity=Decimal("1"),
            requested_price=Decimal("100"),
            risk_status="allowed",
            safety_status="allowed",
            final_status=final_status,
            final_reason="Market buy order filled",
            created_at=created_at or datetime.now(timezone.utc),
        )
    )
    session.commit()
    usage_day = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    usage = (
        session.query(ExecutionDailyQuotaUsage)
        .filter(ExecutionDailyQuotaUsage.bot_id == bot_id, ExecutionDailyQuotaUsage.utc_day == usage_day)
        .one_or_none()
    )
    if usage is None:
        usage = ExecutionDailyQuotaUsage(bot_id=bot_id, utc_day=usage_day, accepted_order_count=0)
    usage.accepted_order_count += 1
    session.add(usage)
    session.commit()


def test_global_execution_safety_status_returns_safe_defaults(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(
        BINANCE_TESTNET_BROKER_ENABLED=False,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=False,
        BINANCE_TESTNET_API_KEY=None,
        BINANCE_TESTNET_API_SECRET=None,
        BINANCE_TESTNET_DRY_RUN_ENABLED=False,
    )
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-safety/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == EXECUTION_SAFETY_STATUS_PUBLIC_FIELDS
    assert body["global_execution_enabled"] is True
    assert body["live_execution_enabled"] is False
    assert body["paper_trading_enabled"] is True
    assert body["paper_execution_allowed"] is True
    assert body["binance_testnet_broker_enabled"] is False
    assert body["binance_testnet_order_submission_enabled"] is False
    assert body["binance_testnet_credentials_configured"] is False
    assert body["binance_testnet_dry_run_enabled"] is False
    assert body["max_order_notional"] is None
    assert body["max_daily_order_count"] is None
    assert body["max_daily_loss"] is None
    assert body["current_daily_attempt_count"] == 0
    assert body["remaining_daily_order_capacity"] is None
    assert body["current_daily_realized_pnl"] == "0"
    assert body["current_daily_realized_loss"] == "0"
    assert body["remaining_daily_loss_capacity"] is None
    assert body["is_daily_loss_limit_exceeded"] is False
    assert body["is_execution_currently_allowed"] is True
    assert body["blocking_reason"] is None


def test_execution_safety_status_reports_paper_trading_disabled(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(
        PAPER_TRADING_ENABLED=False,
        BINANCE_TESTNET_BROKER_ENABLED=False,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=False,
    )
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-safety/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == EXECUTION_SAFETY_STATUS_PUBLIC_FIELDS
    assert body["paper_trading_enabled"] is False
    assert body["paper_execution_allowed"] is False
    assert body["is_execution_currently_allowed"] is False
    assert body["blocking_reason"] == "paper_trading_disabled"
    assert body["live_execution_enabled"] is False
    assert body["binance_testnet_broker_enabled"] is False
    assert body["binance_testnet_order_submission_enabled"] is False


def test_execution_safety_status_reports_configured_daily_capacity(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=2, EXECUTION_MAX_ORDER_NOTIONAL="25")
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    with db_session_factory() as session:
        add_execution_attempt(session, bot_id=None)

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-safety/status", params={"quantity": "0.1", "market_price": "100"})

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trading_enabled"] is True
    assert body["max_daily_order_count"] == 2
    assert body["max_order_notional"] == "25"
    assert body["current_daily_attempt_count"] == 1
    assert body["remaining_daily_order_capacity"] == 1
    assert body["is_execution_currently_allowed"] is True


def test_bot_execution_safety_status_counts_only_that_bot(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=2)
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        _, other_bot, _ = bot_stack_factory(session, name="Other Bot")
        add_execution_attempt(session, bot_id=bot.id)
        add_execution_attempt(session, bot_id=other_bot.id)
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot_id}/execution-safety/status")

    assert response.status_code == 200
    body = response.json()
    assert body["current_daily_attempt_count"] == 1
    assert body["remaining_daily_order_capacity"] == 1
    assert body["is_execution_currently_allowed"] is True


def test_execution_safety_status_counts_current_utc_day_only(db_session) -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    add_execution_attempt(db_session, bot_id=1, created_at=now)
    add_execution_attempt(db_session, bot_id=1, created_at=now - timedelta(days=1))
    service = ExecutionSafetyStatusService(
        ExecutionAttemptRepository(db_session),
        Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=2),
        now_provider=lambda: now,
    )

    status = service.get_status(bot_id=1)

    assert status.utc_day_start == datetime(2026, 5, 27, tzinfo=timezone.utc)
    assert status.current_daily_attempt_count == 1
    assert status.remaining_daily_order_capacity == 1


def test_execution_safety_status_reports_daily_loss_state(db_session) -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("90"),
            realized_pnl_delta=Decimal("-7"),
            occurred_at=now,
        )
    )
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("120"),
            realized_pnl_delta=Decimal("2"),
            occurred_at=now,
        )
    )
    db_session.commit()
    service = ExecutionSafetyStatusService(
        ExecutionAttemptRepository(db_session),
        Settings(EXECUTION_MAX_DAILY_LOSS="10"),
        paper_accounting_repository=PaperAccountingRepository(db_session),
        now_provider=lambda: now,
    )

    status = service.get_status(side="buy")

    assert status.utc_day_start == datetime(2026, 5, 27, tzinfo=timezone.utc)
    assert status.max_daily_loss == Decimal("10")
    assert status.current_daily_realized_pnl == Decimal("-5.00000000")
    assert status.current_daily_realized_loss == Decimal("5.00000000")
    assert status.remaining_daily_loss_capacity == Decimal("5.00000000")
    assert status.is_daily_loss_limit_exceeded is False
    assert status.is_execution_currently_allowed is True


def test_execution_safety_status_reports_daily_loss_block(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_LOSS="10")
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    with db_session_factory() as session:
        session.add(
            PaperAccountingEvent(
                symbol="BTCUSDT",
                side="sell",
                mode="paper",
                event_type="fill_applied",
                cash_delta=Decimal("90"),
                realized_pnl_delta=Decimal("-10"),
                occurred_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-safety/status", params={"side": "buy"})

    assert response.status_code == 200
    body = response.json()
    assert body["max_daily_loss"] == "10"
    assert body["current_daily_realized_pnl"] == "-10.00000000"
    assert body["current_daily_realized_loss"] == "10.00000000"
    assert body["remaining_daily_loss_capacity"] == "0"
    assert body["is_daily_loss_limit_exceeded"] is True
    assert body["is_execution_currently_allowed"] is False
    assert body["blocking_reason"] == "max_daily_loss_exceeded"


def test_execution_safety_status_allows_sell_when_daily_loss_limit_is_reached(db_session) -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("90"),
            realized_pnl_delta=Decimal("-10"),
            occurred_at=now,
        )
    )
    db_session.commit()
    service = ExecutionSafetyStatusService(
        ExecutionAttemptRepository(db_session),
        Settings(EXECUTION_MAX_DAILY_LOSS="10"),
        paper_accounting_repository=PaperAccountingRepository(db_session),
        now_provider=lambda: now,
    )

    status = service.get_status(side="sell")

    assert status.is_daily_loss_limit_exceeded is True
    assert status.is_execution_currently_allowed is True


def test_execution_safety_status_reports_blocked_when_daily_limit_reached(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=1)
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        add_execution_attempt(session, bot_id=bot.id)
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot_id}/execution-safety/status")
        sell_response = client.get(f"/api/v1/bots/{bot_id}/execution-safety/status", params={"side": "sell"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_daily_attempt_count"] == 1
    assert body["remaining_daily_order_capacity"] == 0
    assert body["is_execution_currently_allowed"] is False
    assert body["blocking_reason"] == "max_daily_order_count_exceeded"

    assert sell_response.status_code == 200
    sell_body = sell_response.json()
    assert sell_body["current_daily_attempt_count"] == 1
    assert sell_body["remaining_daily_order_capacity"] == 0
    assert sell_body["is_execution_currently_allowed"] is True
    assert sell_body["blocking_reason"] is None
    assert sell_body["metadata"]["risk_reducing_exits_allowed"] is True


def test_execution_safety_status_unknown_bot_returns_404(
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/bots/999999/execution-safety/status")

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_execution_safety_status_reports_testnet_dry_run_without_leaking_credentials_or_mutating_state(
    db_session,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
    monkeypatch,
) -> None:
    settings = Settings(
        BINANCE_TESTNET_API_KEY="super-secret-key",
        BINANCE_TESTNET_API_SECRET="super-secret-secret",
        BINANCE_TESTNET_DRY_RUN_ENABLED=True,
    )
    import app.api.v1.endpoints.execution_safety as endpoint

    monkeypatch.setattr(endpoint, "get_settings", lambda: settings)
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get("/api/v1/execution-safety/status")

    assert response.status_code == 200
    serialized = response.text
    body = response.json()
    assert body["binance_testnet_credentials_configured"] is True
    assert body["binance_testnet_dry_run_enabled"] is True
    assert body["paper_trading_enabled"] is True
    assert "super-secret-key" not in serialized
    assert "super-secret-secret" not in serialized
    assert ExecutionAttemptRepository(db_session).list_filtered() == []
    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
