import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
from app.models.execution_attempt import ExecutionAttempt
from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.models.paper_accounting_event import PaperAccountingEvent
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.base import BrokerOrderIntent
from app.services.brokers.binance import (
    BinanceInvalidOrderResponseError,
    BinanceOrderHttpResponse,
    BinanceRequestSigner,
    BinanceSignedRequestBuilder,
    BinanceTestnetBroker,
    BinanceTestnetBrokerConfig,
    BinanceTestnetOrderClient,
    BinanceTestnetOrderClientError,
)
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.core.config import Settings
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.portfolio_account import PortfolioAccountService
from app.services.portfolio import PortfolioService
from app.services.execution_attempt import ExecutionAttemptService
from app.services.simulated_execution import PaperExecutionBroker, PaperExecutionService


FIXED_NOW = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
TEST_SECRET = "test-secret"


class RecordingOrderClient:
    def __init__(self, response: BinanceOrderHttpResponse | None = None, exception: Exception | None = None):
        self.response = response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 12345,
                "status": "FILLED",
                "executedQty": "0.1",
                "cummulativeQuoteQty": "10",
                "fills": [{"price": "100", "qty": "0.1", "commission": "0.001"}],
            },
        )
        self.exception = exception
        self.calls: list[dict] = []

    def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        return self.response


def enabled_binance_config(**overrides) -> BinanceTestnetBrokerConfig:
    values = {
        "enabled": True,
        "order_submission_enabled": True,
        "api_key": "test-key",
        "api_secret": "test-secret",
    }
    values.update(overrides)
    return BinanceTestnetBrokerConfig(**values)


def add_attempt(
    session,
    *,
    bot_id: int | None,
    final_status: str = "filled",
    created_at: datetime = FIXED_NOW,
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
            created_at=created_at,
        )
    )
    session.commit()
    usage_day = created_at.astimezone(timezone.utc).date()
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


def build_daily_limit_guard(
    db_session,
    *,
    max_daily_order_count: int,
    max_order_notional: Decimal | None = None,
) -> ExecutionSafetyGuard:
    return ExecutionSafetyGuard(
        ExecutionSafetyConfig(
            max_daily_order_count=max_daily_order_count,
            max_order_notional=max_order_notional,
        ),
        daily_limit_service=ExecutionDailyLimitService(
            ExecutionAttemptRepository(db_session),
            now_provider=lambda: FIXED_NOW,
        ),
    )


def build_daily_loss_guard(
    db_session,
    *,
    max_daily_loss: Decimal | None,
    now=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
) -> ExecutionSafetyGuard:
    return ExecutionSafetyGuard(
        ExecutionSafetyConfig(max_daily_loss=max_daily_loss),
        daily_limit_service=ExecutionDailyLimitService(
            ExecutionAttemptRepository(db_session),
            paper_accounting_repository=PaperAccountingRepository(db_session),
            now_provider=lambda: now,
        ),
    )


def build_paper_broker(
    db_session,
    stub_market_data_service,
    *,
    max_daily_loss: Decimal | None,
    starting_cash: Decimal = Decimal("1000.00"),
    now=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
) -> PaperExecutionBroker:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=starting_cash)
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    return PaperExecutionBroker(
        service,
        safety_guard=build_daily_loss_guard(db_session, max_daily_loss=max_daily_loss, now=now),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )


def test_paper_execution_broker_returns_normalized_filled_result(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = PaperExecutionBroker(service).submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    position = repository.get_position_by_symbol("BTCUSDT")
    fills = repository.list_fills()
    assert result.accepted is True
    assert result.status == "filled"
    assert result.order_id is not None
    assert result.executed_quantity == Decimal("1.00000000")
    assert result.executed_price == Decimal("100.00000000")
    assert result.fee == Decimal("0E-8")
    assert result.metadata["broker"] == "paper"
    assert result.metadata["fill_id"] == fills[0].id
    assert position is not None
    assert position.quantity == Decimal("1.00000000")


def test_paper_execution_broker_buy_and_sell_consume_daily_slots(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    broker = PaperExecutionBroker(
        service,
        safety_guard=build_daily_limit_guard(db_session, max_daily_order_count=2),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )
    stub_market_data_service.set_price("BTCUSDT", "100.00")

    buy = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    sell = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))
    blocked = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=7, limit=10)
    count = ExecutionDailyLimitService(
        ExecutionAttemptRepository(db_session),
        now_provider=lambda: FIXED_NOW,
    ).count_successful_orders_today(bot_id=7)
    assert buy.accepted is True
    assert sell.accepted is True
    assert blocked.accepted is False
    assert blocked.reason == "max_daily_order_count_exceeded"
    assert count.count == 2
    assert [attempt.final_status for attempt in attempts] == ["blocked_by_safety", "filled", "filled"]


def test_paper_execution_broker_allows_partial_and_full_sell_after_daily_count_exhausted(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    broker = PaperExecutionBroker(
        service,
        safety_guard=build_daily_limit_guard(db_session, max_daily_order_count=1),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )
    stub_market_data_service.set_price("BTCUSDT", "100.00")

    buy = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("2")))
    blocked_buy = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    partial_sell = broker.submit_market_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="sell", quantity=Decimal("0.75"))
    )
    full_sell = broker.submit_market_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="sell", quantity=Decimal("1.25"))
    )
    oversell = broker.submit_market_order(BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    position = repository.get_position_by_symbol("BTCUSDT")
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=7, limit=10)
    events = PaperAccountingRepository(db_session).list_events()
    assert buy.accepted is True
    assert blocked_buy.accepted is False
    assert blocked_buy.reason == "max_daily_order_count_exceeded"
    assert partial_sell.accepted is True
    assert full_sell.accepted is True
    assert oversell.accepted is False
    assert oversell.reason == "Insufficient position quantity for this sell order"
    assert position is not None
    assert position.quantity == Decimal("0E-8")
    assert len(events) == 3
    assert [attempt.final_status for attempt in attempts] == [
        "rejected_by_broker",
        "filled",
        "filled",
        "blocked_by_safety",
        "filled",
    ]
    assert attempts[1].metadata_["risk_reducing_exit"] is True
    assert attempts[2].metadata_["risk_reducing_exit"] is True


def test_execution_safety_guard_allows_normal_paper_execution_by_default() -> None:
    decision = ExecutionSafetyGuard().validate_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_execution_safety_guard_rejects_live_mode_by_default() -> None:
    decision = ExecutionSafetyGuard().validate_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="live"),
        broker="binance_live",
        market_price=Decimal("100"),
    )

    assert decision.allowed is False
    assert decision.reason == "live_execution_disabled"


def test_execution_safety_guard_rejects_testnet_submission_when_disabled() -> None:
    decision = ExecutionSafetyGuard().validate_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="testnet"),
        broker="binance_testnet",
        market_price=Decimal("100"),
    )

    assert decision.allowed is False
    assert decision.reason == "testnet_order_submission_disabled"


def test_execution_safety_guard_rejects_invalid_quantity() -> None:
    decision = ExecutionSafetyGuard().validate_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is False
    assert decision.reason == "invalid_order_quantity"


def test_execution_safety_guard_rejects_max_notional_exceeded() -> None:
    guard = ExecutionSafetyGuard(ExecutionSafetyConfig(max_order_notional=Decimal("10")))

    decision = guard.validate_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.2"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is False
    assert decision.reason == "max_order_notional_exceeded"
    assert decision.metadata["notional"] == "20.0"
    assert decision.metadata["max_order_notional"] == "10"


def test_execution_safety_guard_allows_when_daily_order_limit_unset(db_session) -> None:
    add_attempt(db_session, bot_id=7)
    guard = ExecutionSafetyGuard(
        ExecutionSafetyConfig(max_daily_order_count=None),
        daily_limit_service=ExecutionDailyLimitService(ExecutionAttemptRepository(db_session), now_provider=lambda: FIXED_NOW),
    )

    decision = guard.validate_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is True


def test_execution_safety_guard_rejects_max_daily_order_count(db_session) -> None:
    add_attempt(db_session, bot_id=7)
    guard = build_daily_limit_guard(db_session, max_daily_order_count=1)

    decision = guard.validate_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is False
    assert decision.reason == "max_daily_order_count_exceeded"
    assert decision.metadata["daily_order_count"] == 1
    assert decision.metadata["max_daily_order_count"] == 1


def test_execution_safety_guard_allows_sell_when_daily_order_count_exhausted(db_session) -> None:
    add_attempt(db_session, bot_id=7)
    guard = build_daily_limit_guard(db_session, max_daily_order_count=1)

    decision = guard.validate_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="sell", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert decision.metadata["risk_reducing_exits_allowed"] is True


def test_execution_safety_guard_daily_order_count_is_bot_scoped(db_session) -> None:
    add_attempt(db_session, bot_id=7)
    guard = build_daily_limit_guard(db_session, max_daily_order_count=1)

    decision = guard.validate_order(
        BrokerOrderIntent(bot_id=8, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is True


def test_execution_safety_guard_daily_order_count_uses_current_utc_day_only(db_session) -> None:
    add_attempt(db_session, bot_id=7, created_at=FIXED_NOW - timedelta(days=1))
    guard = build_daily_limit_guard(db_session, max_daily_order_count=1)

    decision = guard.validate_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), mode="paper"),
        broker="paper",
        market_price=Decimal("100"),
    )

    assert decision.allowed is True


def test_paper_execution_broker_daily_order_limit_blocks_without_order_or_fill(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    add_attempt(db_session, bot_id=7)
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    guard = build_daily_limit_guard(db_session, max_daily_order_count=1)
    attempt_service = ExecutionAttemptService(ExecutionAttemptRepository(db_session))

    result = PaperExecutionBroker(service, safety_guard=guard, attempt_service=attempt_service).submit_market_order(
        BrokerOrderIntent(bot_id=7, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=7, final_status="blocked_by_safety")
    assert result.accepted is False
    assert result.reason == "max_daily_order_count_exceeded"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert len(attempts) == 1
    assert attempts[0].final_reason == "max_daily_order_count_exceeded"
    assert attempts[0].order_id is None


def test_daily_loss_disabled_preserves_paper_buy_behavior(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=None)
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is True
    assert len(PortfolioRepository(db_session).list_orders()) == 1
    assert len(PortfolioRepository(db_session).list_fills()) == 1


def test_positive_realized_pnl_does_not_consume_daily_loss_capacity(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "115")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    stub_market_data_service.set_price("BTCUSDT", "120")
    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    loss_snapshot = broker.safety_guard.daily_limit_service.get_realized_loss_today()
    assert loss_snapshot.realized_pnl == Decimal("15.00000000")
    assert loss_snapshot.realized_loss == Decimal("0")
    assert result.accepted is True


def test_realized_sell_loss_consumes_daily_loss_capacity(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("20"))
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    loss_snapshot = broker.safety_guard.daily_limit_service.get_realized_loss_today()

    assert loss_snapshot.realized_pnl == Decimal("-10.00000000")
    assert loss_snapshot.realized_loss == Decimal("10.00000000")


def test_reaching_daily_loss_limit_blocks_later_buy_without_order_fill_or_mutation(
    db_session,
    stub_market_data_service,
) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))
    cash_before = repository.get_account().cash_balance
    position_before = repository.get_position_by_symbol("BTCUSDT").quantity
    order_count_before = len(repository.list_orders())
    fill_count_before = len(repository.list_fills())

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    attempts = ExecutionAttemptRepository(db_session).list_filtered(final_status="blocked_by_safety")
    assert result.accepted is False
    assert result.reason == "max_daily_loss_exceeded"
    assert len(repository.list_orders()) == order_count_before
    assert len(repository.list_fills()) == fill_count_before
    assert repository.get_account().cash_balance == cash_before
    assert repository.get_position_by_symbol("BTCUSDT").quantity == position_before
    assert len(attempts) == 1
    assert attempts[0].final_reason == "max_daily_loss_exceeded"
    assert attempts[0].safety_status == "max_daily_loss_exceeded"
    assert attempts[0].order_id is None


def test_exceeding_daily_loss_limit_blocks_later_buy(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("5"))
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is False
    assert result.reason == "max_daily_loss_exceeded"


def test_sell_remains_allowed_after_daily_loss_limit_is_reached(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("2")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    assert result.accepted is True
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("0E-8")


def test_daily_loss_limit_does_not_bypass_oversell_rejection(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    assert result.accepted is False
    assert result.reason == "Insufficient position quantity for this sell order"


def test_daily_loss_uses_current_utc_day_only(db_session) -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("90"),
            realized_pnl_delta=Decimal("-10"),
            occurred_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("95"),
            realized_pnl_delta=Decimal("-5"),
            occurred_at=now,
        )
    )
    db_session.commit()
    snapshot = ExecutionDailyLimitService(
        ExecutionAttemptRepository(db_session),
        paper_accounting_repository=PaperAccountingRepository(db_session),
        now_provider=lambda: now,
    ).get_realized_loss_today()

    assert snapshot.day_start == datetime(2026, 5, 27, tzinfo=timezone.utc)
    assert snapshot.realized_pnl == Decimal("-5.00000000")
    assert snapshot.realized_loss == Decimal("5.00000000")


def test_prior_day_realized_losses_do_not_block_today(db_session, stub_market_data_service) -> None:
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    db_session.add(
        PaperAccountingEvent(
            symbol="BTCUSDT",
            side="sell",
            mode="paper",
            event_type="fill_applied",
            cash_delta=Decimal("90"),
            realized_pnl_delta=Decimal("-10"),
            occurred_at=now - timedelta(days=1),
        )
    )
    db_session.commit()
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"), now=now)
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is True


def test_daily_loss_is_shared_across_bots(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=2, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is False
    assert result.reason == "max_daily_loss_exceeded"


def test_paper_portfolio_reset_does_not_bypass_same_day_daily_loss(db_session, stub_market_data_service) -> None:
    broker = build_paper_broker(db_session, stub_market_data_service, max_daily_loss=Decimal("10"))
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    stub_market_data_service.set_price("BTCUSDT", "90")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    reset = PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("1000"))
    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert reset.cash_balance == Decimal("1000.00000000")
    assert len(PaperAccountingRepository(db_session).list_events()) == 2
    assert result.accepted is False
    assert result.reason == "max_daily_loss_exceeded"


def test_paper_execution_broker_rejects_when_global_kill_switch_is_disabled(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    guard = ExecutionSafetyGuard(ExecutionSafetyConfig(global_enabled=False))
    attempt_service = ExecutionAttemptService(ExecutionAttemptRepository(db_session))

    result = PaperExecutionBroker(service, safety_guard=guard, attempt_service=attempt_service).submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assert result.accepted is False
    assert result.reason == "execution_global_disabled"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert len(attempts) == 1
    assert attempts[0].final_status == "blocked_by_safety"
    assert attempts[0].final_reason == "execution_global_disabled"
    assert attempts[0].order_id is None


def test_binance_request_signer_generates_hmac_sha256_signature() -> None:
    signer = BinanceRequestSigner(TEST_SECRET, timestamp_provider=lambda: 1710000000000)
    params = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "quantity": "0.1",
        "timestamp": 1710000000000,
        "recvWindow": 5000,
    }

    signature = signer.sign(params)

    assert signature == "da50f6c7e53ba982bc140d1ac54e932b93651b5bef77f35c40179a19144537b1"


def test_binance_signed_request_builder_includes_timestamp_recv_window_and_signature() -> None:
    original_payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "quantity": "0.1",
    }
    builder = BinanceSignedRequestBuilder(
        BinanceRequestSigner(TEST_SECRET, timestamp_provider=lambda: 1710000000000),
        recv_window=6000,
    )

    signed = builder.signed_params(original_payload)

    assert signed["timestamp"] == 1710000000000
    assert signed["recvWindow"] == 6000
    assert signed["signature"] == "d9d74c95fbbebf27e17f83911b7097113674a0e8e2567fd1da283a8195f3eab0"
    assert "timestamp" not in original_payload
    assert "recvWindow" not in original_payload
    assert "signature" not in original_payload


def test_binance_market_order_builder_constructs_market_payload() -> None:
    builder = BinanceSignedRequestBuilder(BinanceRequestSigner(TEST_SECRET, timestamp_provider=lambda: 1710000000000))

    params = builder.market_order_params(symbol="btcusdt", side="buy", quantity=Decimal("0.1000"))

    assert params["symbol"] == "BTCUSDT"
    assert params["side"] == "BUY"
    assert params["type"] == "MARKET"
    assert params["quantity"] == "0.1"
    assert params["timestamp"] == 1710000000000
    assert params["recvWindow"] == 5000
    assert "signature" in params


def test_binance_testnet_broker_disabled_by_default_rejects_without_http_call() -> None:
    class ExplodingHttpClient:
        def post(self, *args, **kwargs):
            raise AssertionError("Binance HTTP order placement must not be called")

    broker = BinanceTestnetBroker(BinanceTestnetBrokerConfig(), http_client=ExplodingHttpClient())

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "testnet_broker_disabled"
    assert result.external_order_id is None


def test_binance_testnet_broker_disabled_records_attempt_without_order(db_session) -> None:
    broker = BinanceTestnetBroker(
        BinanceTestnetBrokerConfig(),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.accepted is False
    assert len(attempts) == 1
    assert attempts[0].bot_id is None
    assert attempts[0].strategy_id is None
    assert attempts[0].mode == "testnet"
    assert attempts[0].broker == "binance_testnet"
    assert attempts[0].final_status == "blocked_by_safety"
    assert attempts[0].final_reason == "testnet_broker_disabled"
    assert attempts[0].order_id is None


def test_binance_testnet_broker_missing_credentials_rejects_safely() -> None:
    client = RecordingOrderClient()
    broker = BinanceTestnetBroker(
        BinanceTestnetBrokerConfig(
            enabled=True,
            order_submission_enabled=True,
            api_key=None,
            api_secret=None,
        ),
        http_client=client,
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="sell", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "missing_testnet_credentials"
    assert result.message == "Binance testnet API credentials are not configured"
    assert client.calls == []


def test_binance_testnet_broker_respects_safety_guard() -> None:
    broker = BinanceTestnetBroker(
        BinanceTestnetBrokerConfig(
            enabled=True,
            order_submission_enabled=True,
            api_key="test-key",
            api_secret="test-secret",
        ),
        safety_guard=ExecutionSafetyGuard(ExecutionSafetyConfig(testnet_order_submission_enabled=False)),
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "testnet_order_submission_disabled"


def test_binance_testnet_broker_order_submission_still_not_implemented_with_credentials() -> None:
    broker = BinanceTestnetBroker(
        enabled_binance_config()
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "testnet_order_submission_not_implemented"
    assert result.metadata["endpoint_path"] == "/api/v3/order"
    assert result.metadata["method"] == "POST"
    assert result.metadata["has_signature"] is True
    assert result.metadata["credentials_configured"] is True
    assert "test-secret" not in str(result.metadata)


def test_binance_testnet_broker_dry_run_prepares_signed_request_without_network_or_secret_leak(db_session) -> None:
    class ExplodingHttpClient:
        def post(self, *args, **kwargs):
            raise AssertionError("Dry-run must not make network calls")

    broker = BinanceTestnetBroker(
        enabled_binance_config(dry_run_enabled=True),
        http_client=ExplodingHttpClient(),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=None, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.accepted is False
    assert result.reason == "testnet_order_submission_dry_run"
    assert result.metadata["endpoint_path"] == "/api/v3/order"
    assert result.metadata["method"] == "POST"
    assert result.metadata["symbol"] == "BTCUSDT"
    assert result.metadata["side"] == "BUY"
    assert result.metadata["order_type"] == "MARKET"
    assert result.metadata["has_signature"] is True
    assert result.metadata["credentials_configured"] is True
    assert "test-secret" not in str(result.metadata)
    assert len(attempts) == 1
    assert "test-secret" not in str(attempts[0].metadata_)


def test_binance_order_client_posts_signed_order_with_api_key_header() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        captured["form"] = parse_qs(request.content.decode())
        return httpx.Response(200, json={"orderId": 1, "executedQty": "0", "status": "NEW"})

    client = BinanceTestnetOrderClient(
        base_url="https://testnet.binance.vision",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    response = client.submit_signed_market_order(
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.1",
            "timestamp": 1710000000000,
            "recvWindow": 5000,
            "signature": "abc123",
        }
    )

    assert response.status_code == 200
    assert response.payload["orderId"] == 1
    assert captured["path"] == "/api/v3/order"
    assert captured["api_key"] == "test-key"
    assert captured["form"]["signature"] == ["abc123"]


def test_binance_testnet_broker_enabled_mocked_submission_normalizes_success(db_session) -> None:
    client = RecordingOrderClient()
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert len(client.calls) == 1
    assert client.calls[0]["symbol"] == "BTCUSDT"
    assert client.calls[0]["side"] == "BUY"
    assert client.calls[0]["type"] == "MARKET"
    assert client.calls[0]["quantity"] == "0.1"
    assert "signature" in client.calls[0]
    assert result.accepted is True
    assert result.status == "submitted"
    assert result.external_order_id == "12345"
    assert result.executed_quantity == Decimal("0.1")
    assert result.executed_price == Decimal("100")
    assert result.fee == Decimal("0.001")
    assert result.metadata["status_code"] == 200
    assert result.metadata["exchange_status"] == "FILLED"
    assert "test-secret" not in str(result.metadata)
    assert len(attempts) == 1
    assert attempts[0].final_status == "order_created"
    assert "test-secret" not in str(attempts[0].metadata_)


def test_binance_testnet_broker_error_json_normalizes_rejection() -> None:
    client = RecordingOrderClient(
        response=BinanceOrderHttpResponse(
            status_code=400,
            payload={"code": -2010, "msg": "Account has insufficient balance"},
        )
    )
    broker = BinanceTestnetBroker(enabled_binance_config(), http_client=client)

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.reason == "binance_testnet_order_rejected"
    assert result.message == "Binance testnet order rejected: Account has insufficient balance"
    assert result.metadata["status_code"] == 400
    assert result.metadata["binance_code"] == -2010


def test_binance_testnet_broker_non_2xx_without_error_message_normalizes_safely() -> None:
    client = RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=500, payload={}))
    broker = BinanceTestnetBroker(enabled_binance_config(), http_client=client)

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.reason == "binance_testnet_order_rejected"
    assert result.message == "Binance testnet order request failed with status 500"
    assert result.metadata["status_code"] == 500


def test_binance_testnet_broker_invalid_json_normalizes_safely() -> None:
    client = RecordingOrderClient(exception=BinanceInvalidOrderResponseError("Invalid JSON"))
    broker = BinanceTestnetBroker(enabled_binance_config(), http_client=client)

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.reason == "invalid_binance_response"
    assert result.metadata["error_type"] == "BinanceInvalidOrderResponseError"


def test_binance_testnet_broker_network_error_normalizes_safely() -> None:
    client = RecordingOrderClient(exception=BinanceTestnetOrderClientError("timeout"))
    broker = BinanceTestnetBroker(enabled_binance_config(), http_client=client)

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.reason == "binance_testnet_request_failed"
    assert result.metadata["error_type"] == "BinanceTestnetOrderClientError"


def test_bot_runner_does_not_call_binance_order_placement_by_default(
    db_session,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    funded_account,
    monkeypatch,
) -> None:
    def fail_if_called(self, intent):
        raise AssertionError("Bot runner must not call Binance order placement by default")

    monkeypatch.setattr(BinanceTestnetBroker, "submit_market_order", fail_if_called)
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session, is_paper=False)
    runner = bot_runner_factory()
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    assert PortfolioRepository(db_session).list_orders() == []


def test_execution_config_defaults_are_safe() -> None:
    assert Settings.model_fields["execution_global_enabled"].default is True
    assert Settings.model_fields["execution_live_enabled"].default is False
    assert Settings.model_fields["execution_max_order_notional"].default is None
    assert Settings.model_fields["execution_max_daily_order_count"].default is None
    assert Settings.model_fields["execution_max_daily_loss"].default is None
    assert Settings.model_fields["binance_testnet_broker_enabled"].default is False
    assert Settings.model_fields["binance_testnet_order_submission_enabled"].default is False
