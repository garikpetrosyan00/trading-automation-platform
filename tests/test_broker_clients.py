import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest
from app.models.execution_attempt import ExecutionAttempt
from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.models.paper_accounting_event import PaperAccountingEvent
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.base import BrokerOrderIntent
from app.services.brokers.binance import (
    BinanceAccountHttpResponse,
    BinanceInvalidAccountResponseError,
    BinanceInvalidOrderResponseError,
    BinanceInvalidOrderQueryResponseError,
    BinanceOrderHttpResponse,
    BinanceRequestSigner,
    BinanceSignedRequestBuilder,
    BinanceTestnetAccountClient,
    BinanceTestnetAccountClientError,
    BinanceTestnetBroker,
    BinanceTestnetBrokerConfig,
    BinanceTestnetOrderClient,
    BinanceTestnetOrderClientError,
    BinanceTestnetOrderQueryClientError,
)
from app.services.brokers.binance_exchange_info import (
    BinanceExchangeInfo,
    BinanceExchangeInfoError,
    BinanceExchangeInfoProvider,
    BinanceQuantityFilter,
    BinanceSymbolRules,
)
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.core.config import Settings
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.execution_reconciliation_worker import ExecutionReconciliationWorkerService
from app.services.portfolio_account import PortfolioAccountService
from app.services.portfolio import PortfolioService
from app.services.execution_attempt import ExecutionAttemptService
from app.services.simulated_execution import PaperExecutionBroker, PaperExecutionService


FIXED_NOW = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
TEST_SECRET = "test-secret"


class RecordingOrderClient:
    def __init__(
        self,
        response: BinanceOrderHttpResponse | None = None,
        exception: Exception | None = None,
        query_response: BinanceOrderHttpResponse | None = None,
        query_exception: Exception | None = None,
    ):
        self.response = response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 12345,
                "clientOrderId": "filled-by-submit-call",
                "status": "FILLED",
                "executedQty": "0.1",
                "cummulativeQuoteQty": "10",
                "fills": [{"price": "100", "qty": "0.1", "commission": "0.001"}],
            },
        )
        self.exception = exception
        self.query_response = query_response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 12345,
                "clientOrderId": "filled-by-submit-call",
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
            },
        )
        self.query_exception = query_exception
        self.calls: list[dict] = []
        self.query_calls: list[dict] = []

    def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        payload = dict(self.response.payload or {})
        if payload.get("clientOrderId") == "filled-by-submit-call":
            payload["clientOrderId"] = params["newClientOrderId"]
        return BinanceOrderHttpResponse(status_code=self.response.status_code, payload=payload)

    def query_signed_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.query_calls.append(params)
        if self.query_exception is not None:
            raise self.query_exception
        payload = dict(self.query_response.payload or {})
        if payload.get("clientOrderId") == "filled-by-submit-call" and self.calls:
            payload["clientOrderId"] = self.calls[0]["newClientOrderId"]
        return BinanceOrderHttpResponse(status_code=self.query_response.status_code, payload=payload)


class RecordingAccountClient:
    def __init__(self, response: BinanceAccountHttpResponse | None = None, exception: Exception | None = None):
        self.response = response or BinanceAccountHttpResponse(
            status_code=200,
            payload={
                "canTrade": True,
                "balances": [
                    {"asset": "BTC", "free": "10", "locked": "0"},
                    {"asset": "USDT", "free": "100000", "locked": "0"},
                ],
            },
        )
        self.exception = exception
        self.calls: list[dict] = []

    def fetch_signed_account(self, params: dict) -> BinanceAccountHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        return self.response


class StaticExchangeInfoProvider:
    def __init__(self, info: BinanceExchangeInfo | None = None, exception: Exception | None = None):
        self.info = info or BinanceExchangeInfo(
            symbols={
                "BTCUSDT": BinanceSymbolRules(
                    symbol="BTCUSDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    status="TRADING",
                    order_types=frozenset({"LIMIT", "MARKET"}),
                )
            }
        )
        self.exception = exception
        self.calls = 0

    def get_exchange_info(self) -> BinanceExchangeInfo:
        self.calls += 1
        if self.exception is not None:
            raise self.exception
        return self.info


def enabled_binance_config(**overrides) -> BinanceTestnetBrokerConfig:
    values = {
        "enabled": True,
        "order_submission_enabled": True,
        "api_key": "test-key",
        "api_secret": "test-secret",
    }
    values.update(overrides)
    return BinanceTestnetBrokerConfig(**values)


def guarded_testnet_broker(
    db_session,
    http_client,
    *,
    account_client=None,
    exchange_info_provider=None,
    config: BinanceTestnetBrokerConfig | None = None,
    max_daily_order_count: int | None = None,
) -> BinanceTestnetBroker:
    attempt_repository = ExecutionAttemptRepository(db_session)
    safety_guard = ExecutionSafetyGuard(
        ExecutionSafetyConfig(
            testnet_order_submission_enabled=True,
            max_daily_order_count=max_daily_order_count,
        ),
        daily_limit_service=ExecutionDailyLimitService(attempt_repository, now_provider=lambda: FIXED_NOW),
    )
    return BinanceTestnetBroker(
        config or enabled_binance_config(),
        http_client=http_client,
        account_client=account_client or RecordingAccountClient(),
        exchange_info_provider=exchange_info_provider or valid_exchange_info_provider(),
        safety_guard=safety_guard,
        attempt_service=ExecutionAttemptService(attempt_repository),
    )


def valid_exchange_info_provider() -> BinanceExchangeInfoProvider:
    return StaticExchangeInfoProvider()  # type: ignore[return-value]


def binance_worker_settings(*, max_attempts: int = 5) -> Settings:
    return Settings(
        BINANCE_TESTNET_BROKER_ENABLED=True,
        BINANCE_TESTNET_ORDER_SUBMISSION_ENABLED=True,
        BINANCE_TESTNET_API_KEY="test-api-key",
        BINANCE_TESTNET_API_SECRET=TEST_SECRET,
        BINANCE_TESTNET_RECONCILIATION_MAX_AUTOMATIC_ATTEMPTS=max_attempts,
    )


def run_delayed_reconciliation(
    db_session,
    *,
    order_client,
    now: datetime,
    max_attempts: int = 5,
):
    worker = ExecutionReconciliationWorkerService(
        ExecutionAttemptRepository(db_session),
        ExecutionReconciliationJobRepository(db_session),
        settings=binance_worker_settings(max_attempts=max_attempts),
        order_client=order_client,
        timestamp_provider=lambda: 1710000000000,
        now_provider=lambda: now,
    )
    return worker.process_due_batch(limit=1)


def quota_count(db_session, *, bot_id: int) -> int:
    usage = (
        db_session.query(ExecutionDailyQuotaUsage)
        .filter(ExecutionDailyQuotaUsage.bot_id == bot_id, ExecutionDailyQuotaUsage.utc_day == FIXED_NOW.date())
        .one_or_none()
    )
    return usage.accepted_order_count if usage is not None else 0


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
        enabled_binance_config(),
        account_client=RecordingAccountClient(),
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "testnet_order_submission_not_implemented"
    assert result.metadata["endpoint_path"] == "/api/v3/order"
    assert result.metadata["method"] == "POST"
    assert result.metadata["signed"] is True
    assert result.metadata["credentials_configured"] is True
    assert "test-secret" not in str(result.metadata)


def test_binance_testnet_broker_dry_run_prepares_signed_request_without_network_or_secret_leak(db_session) -> None:
    class ExplodingHttpClient:
        def __init__(self):
            self.query_calls = []

        def submit_signed_market_order(self, *args, **kwargs):
            raise AssertionError("Dry-run must not make network calls")

        def query_signed_order(self, params):
            self.query_calls.append(params)
            raise AssertionError("Dry-run must not query order status")

    client = ExplodingHttpClient()
    broker = BinanceTestnetBroker(
        enabled_binance_config(dry_run_enabled=True),
        http_client=client,
        account_client=RecordingAccountClient(),
        exchange_info_provider=valid_exchange_info_provider(),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=None, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.accepted is False
    assert result.reason == "testnet_order_submission_dry_run"
    assert client.query_calls == []
    assert result.metadata["endpoint_path"] == "/api/v3/order"
    assert result.metadata["method"] == "POST"
    assert result.metadata["symbol"] == "BTCUSDT"
    assert result.metadata["side"] == "BUY"
    assert result.metadata["order_type"] == "MARKET"
    assert result.metadata["signed"] is True
    assert result.metadata["credentials_configured"] is True
    assert "signature" not in str(result.metadata).lower()
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


def test_binance_order_client_queries_signed_order_with_api_key_header() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        captured["query"] = parse_qs(request.url.query.decode())
        return httpx.Response(
            200,
            json={"symbol": "BTCUSDT", "orderId": 1, "clientOrderId": "tap_original", "status": "NEW"},
        )

    signer = BinanceRequestSigner(TEST_SECRET, timestamp_provider=lambda: 1710000000000)
    params = BinanceSignedRequestBuilder(signer, recv_window=5000).order_query_params(
        symbol="BTCUSDT",
        client_order_id="tap_original",
    )
    client = BinanceTestnetOrderClient(
        base_url="https://testnet.binance.vision",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    response = client.query_signed_order(params)

    assert response.status_code == 200
    assert captured["path"] == "/api/v3/order"
    assert captured["api_key"] == "test-key"
    assert captured["query"]["symbol"] == ["BTCUSDT"]
    assert captured["query"]["origClientOrderId"] == ["tap_original"]
    assert captured["query"]["timestamp"] == ["1710000000000"]
    assert captured["query"]["recvWindow"] == ["5000"]
    assert "signature" in captured["query"]


def test_binance_account_client_gets_signed_account_with_api_key_header() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("X-MBX-APIKEY")
        captured["query"] = parse_qs(request.url.query.decode())
        return httpx.Response(200, json={"canTrade": True, "balances": []})

    signer = BinanceRequestSigner(TEST_SECRET, timestamp_provider=lambda: 1710000000000)
    params = BinanceSignedRequestBuilder(signer, recv_window=5000).account_params()
    client = BinanceTestnetAccountClient(
        base_url="https://testnet.binance.vision",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    response = client.fetch_signed_account(params)

    assert response.status_code == 200
    assert captured["path"] == "/api/v3/account"
    assert captured["api_key"] == "test-key"
    assert captured["query"]["timestamp"] == ["1710000000000"]
    assert captured["query"]["recvWindow"] == ["5000"]
    assert "signature" in captured["query"]


def test_binance_testnet_broker_buy_account_preflight_allows_enough_quote_balance(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    account_client = RecordingAccountClient()
    broker = guarded_testnet_broker(db_session, client, account_client=account_client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert len(account_client.calls) == 1
    assert len(client.calls) == 1
    assert client.query_calls == []
    assert result.metadata["account_preflight_checked"] is True
    assert result.metadata["balance_asset"] == "USDT"
    assert result.metadata["balance_sufficient"] is True


def test_binance_testnet_broker_buy_account_preflight_blocks_insufficient_quote_balance() -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(
            status_code=200,
            payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "9.99", "locked": "100000"}]},
        )
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "testnet_insufficient_balance"
    assert len(account_client.calls) == 1
    assert client.calls == []
    assert client.query_calls == []
    assert result.metadata["balance_asset"] == "USDT"
    assert result.metadata["balance_sufficient"] is False
    assert "locked" not in str(result.metadata).lower()
    assert "9.99" not in str(result.metadata)
    assert "signature" not in str(result.metadata).lower()


def test_binance_testnet_broker_sell_account_preflight_allows_enough_base_balance(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="sell", quantity=Decimal("0.1")))

    assert result.accepted is True
    assert len(client.calls) == 1
    assert result.metadata["balance_asset"] == "BTC"
    assert result.metadata["balance_sufficient"] is True


def test_binance_testnet_broker_sell_account_preflight_blocks_insufficient_base_balance() -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(
            status_code=200,
            payload={"canTrade": True, "balances": [{"asset": "BTC", "free": "0.01", "locked": "10"}]},
        )
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="sell", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.reason == "testnet_insufficient_balance"
    assert client.calls == []
    assert client.query_calls == []
    assert result.metadata["balance_asset"] == "BTC"
    assert result.metadata["balance_sufficient"] is False


def test_binance_testnet_broker_account_preflight_missing_asset_is_zero_balance() -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(status_code=200, payload={"canTrade": True, "balances": [{"asset": "ETH", "free": "100"}]})
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "testnet_insufficient_balance"
    assert client.calls == []
    assert client.query_calls == []
    assert result.metadata["balance_asset"] == "USDT"


def test_binance_testnet_broker_account_preflight_locked_balance_is_not_counted() -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(
            status_code=200,
            payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "0", "locked": "100000"}]},
        )
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "testnet_insufficient_balance"
    assert client.calls == []
    assert client.query_calls == []
    assert "locked" not in str(result.metadata).lower()


@pytest.mark.parametrize(
    ("account_client", "expected_reason"),
    [
        (
            RecordingAccountClient(BinanceAccountHttpResponse(status_code=200, payload={"canTrade": False, "balances": []})),
            "testnet_account_trading_disabled",
        ),
        (
            RecordingAccountClient(BinanceAccountHttpResponse(status_code=200, payload={"canTrade": True, "balances": {}})),
            "testnet_account_response_invalid",
        ),
        (
            RecordingAccountClient(
                BinanceAccountHttpResponse(
                    status_code=200,
                    payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "not-a-number"}]},
                )
            ),
            "testnet_account_response_invalid",
        ),
        (
            RecordingAccountClient(exception=BinanceInvalidAccountResponseError("raw account body")),
            "testnet_account_response_invalid",
        ),
        (
            RecordingAccountClient(BinanceAccountHttpResponse(status_code=500, payload={"msg": "raw account body"})),
            "testnet_account_fetch_failed",
        ),
        (
            RecordingAccountClient(exception=BinanceTestnetAccountClientError("timeout with signed query")),
            "testnet_account_fetch_failed",
        ),
    ],
)
def test_binance_testnet_broker_account_preflight_failures_block_before_order_submission(
    account_client,
    expected_reason,
) -> None:
    client = RecordingOrderClient()
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == expected_reason
    assert client.calls == []
    assert client.query_calls == []
    assert "raw account body" not in str(result.metadata)
    assert "signed query" not in str(result.metadata)
    assert "test-secret" not in str(result.metadata)
    assert "signature" not in str(result.metadata).lower()


def test_binance_testnet_broker_account_preflight_failure_does_not_sign_order(monkeypatch) -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(status_code=200, payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "0"}]})
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
    )

    def fail_if_order_params_are_signed(*args, **kwargs):
        raise AssertionError("Order request must not be signed before account preflight passes")

    monkeypatch.setattr(broker, "_build_signed_market_order_params", fail_if_order_params_are_signed)

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.reason == "testnet_insufficient_balance"
    assert client.calls == []
    assert client.query_calls == []


def test_binance_testnet_broker_account_preflight_failure_persists_only_safe_attempt(db_session) -> None:
    client = RecordingOrderClient()
    account_client = RecordingAccountClient(
        BinanceAccountHttpResponse(
            status_code=200,
            payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "0", "locked": "100000"}]},
        )
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(api_key="safe-test-key"),
        http_client=client,
        account_client=account_client,
        exchange_info_provider=valid_exchange_info_provider(),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.reason == "testnet_insufficient_balance"
    assert client.calls == []
    assert client.query_calls == []
    assert len(attempts) == 1
    assert attempts[0].final_status == "rejected_by_broker"
    assert attempts[0].final_reason == "testnet_insufficient_balance"
    assert attempts[0].metadata_["account_preflight_checked"] is True
    assert attempts[0].metadata_["balance_asset"] == "USDT"
    serialized = str(attempts[0].metadata_)
    assert "safe-test-key" not in serialized
    assert "test-secret" not in serialized
    assert "signature" not in serialized.lower()
    assert "locked" not in serialized.lower()


@pytest.mark.parametrize(
    ("client", "expected_trigger"),
    [
        (RecordingOrderClient(exception=BinanceTestnetOrderClientError("timeout", trigger="timeout")), "timeout"),
        (
            RecordingOrderClient(exception=BinanceTestnetOrderClientError("network", trigger="network_error")),
            "network_error",
        ),
        (RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=500, payload={})), "http_5xx"),
        (
            RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=400, payload={"code": -1006, "msg": "unknown"})),
            "binance_unknown_status_error",
        ),
        (
            RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=400, payload={"code": -1007, "msg": "timeout"})),
            "binance_unknown_status_error",
        ),
        (RecordingOrderClient(exception=BinanceInvalidOrderResponseError("Invalid JSON")), "invalid_success_response"),
        (
            RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=200, payload={"symbol": "BTCUSDT", "status": "NEW"})),
            "invalid_success_response",
        ),
    ],
)
def test_binance_testnet_broker_uncertain_post_outcomes_reconcile_once_and_recover(
    db_session,
    bot_stack_factory,
    client,
    expected_trigger,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert result.reason == "testnet_order_recovered_after_unknown_submission"
    assert result.message == "Binance testnet order recovered after status-unknown submission"
    assert len(client.calls) == 1
    assert len(client.query_calls) == 1
    assert client.query_calls[0]["symbol"] == "BTCUSDT"
    assert client.query_calls[0]["origClientOrderId"] == client.calls[0]["newClientOrderId"]
    assert result.external_order_id == "12345"
    assert result.metadata["submission_status_unknown"] is True
    assert result.metadata["reconciliation_attempted"] is True
    assert result.metadata["reconciliation_trigger"] == expected_trigger
    assert result.metadata["reconciliation_resolution"] == "found"
    assert result.metadata["submission_recovered"] is True
    assert result.metadata["recovered_order_status"] == "NEW"
    assert result.metadata["exchange_status"] == "NEW"
    assert result.metadata["client_order_id"] == client.calls[0]["newClientOrderId"]
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(attempts) == 1
    assert attempts[0].final_status == "order_created"
    assert attempts[0].final_reason == "testnet_order_recovered_after_unknown_submission"
    assert job is not None
    assert job.state == "resolved"
    assert job.last_resolution == "found"
    assert quota_count(db_session, bot_id=bot.id) == 1
    assert "signature" not in str(result.metadata).lower()
    assert "test-secret" not in str(result.metadata)


@pytest.mark.parametrize(
    ("query_response", "query_exception"),
    [
        (
            BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"}),
            None,
        ),
        (None, BinanceTestnetOrderQueryClientError("timeout with signed url")),
        (None, BinanceTestnetOrderQueryClientError("network with signed url")),
        (BinanceOrderHttpResponse(status_code=500, payload={"msg": "raw query body"}), None),
        (None, BinanceInvalidOrderQueryResponseError("raw query body")),
        (BinanceOrderHttpResponse(status_code=200, payload={"symbol": "BTCUSDT", "status": "NEW"}), None),
        (
            BinanceOrderHttpResponse(
                status_code=200,
                payload={"symbol": "ETHUSDT", "orderId": 12345, "clientOrderId": "filled-by-submit-call", "status": "NEW"},
            ),
            None,
        ),
        (
            BinanceOrderHttpResponse(
                status_code=200,
                payload={"symbol": "BTCUSDT", "orderId": 12345, "clientOrderId": "different-id", "status": "NEW"},
            ),
            None,
        ),
    ],
)
def test_binance_testnet_broker_unresolved_reconciliation_fails_closed_without_second_post(
    db_session,
    bot_stack_factory,
    query_response,
    query_exception,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(
        exception=BinanceTestnetOrderClientError("timeout", trigger="timeout"),
        query_response=query_response,
        query_exception=query_exception,
    )
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "testnet_order_reconciliation_unresolved"
    assert result.status == "rejected"
    assert len(client.calls) == 1
    assert len(client.query_calls) == 1
    assert result.metadata["submission_status_unknown"] is True
    assert result.metadata["reconciliation_attempted"] is True
    assert result.metadata["reconciliation_trigger"] == "timeout"
    assert result.metadata["reconciliation_resolution"] == "unresolved"
    assert result.metadata["submission_recovered"] is False
    assert result.metadata["client_order_id"] == client.calls[0]["newClientOrderId"]
    serialized = str(result.metadata)
    assert "raw query body" not in serialized
    assert "signed url" not in serialized
    assert "signature" not in serialized.lower()
    assert "test-secret" not in serialized


def test_binance_testnet_broker_reconciliation_failure_persists_only_safe_attempt(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(
        exception=BinanceTestnetOrderClientError("timeout", trigger="timeout"),
        query_response=BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"}),
    )
    broker = guarded_testnet_broker(db_session, client, config=enabled_binance_config(api_key="safe-test-key"))

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert result.reason == "testnet_order_reconciliation_unresolved"
    assert len(client.calls) == 1
    assert len(client.query_calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "rejected_by_broker"
    assert attempts[0].final_reason == "testnet_order_reconciliation_unresolved"
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert job is not None
    assert job.state == "pending"
    assert quota_count(db_session, bot_id=bot.id) == 0
    serialized = str(attempts[0].metadata_)
    assert "safe-test-key" not in serialized
    assert "test-secret" not in serialized
    assert "signature" not in serialized.lower()
    assert "NO_SUCH_ORDER" not in serialized

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_pre_submit_reservation_is_committed_before_order_post(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")

    class InspectingOrderClient(RecordingOrderClient):
        def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
            attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
            assert len(attempts) == 1
            assert attempts[0].final_status == "created"
            assert attempts[0].final_reason == "testnet_order_submission_reserved"
            assert attempts[0].metadata_["client_order_id"] == params["newClientOrderId"]
            assert attempts[0].metadata_["submission_phase"] == "pre_submit_reserved"
            job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
            assert job is not None
            assert job.state == "pending"
            return super().submit_signed_market_order(params)

    client = InspectingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert result.accepted is True
    assert len(client.calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "order_created"
    assert quota_count(db_session, bot_id=bot.id) == 1
    assert job is not None
    assert job.state == "resolved"

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.accepted is True
    assert len(next_client.calls) == 1


def test_binance_testnet_premature_worker_not_found_before_post_keeps_reservation_blocking(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    worker_client = RecordingOrderClient(
        query_response=BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"})
    )
    broker = guarded_testnet_broker(db_session, client)

    def worker_runs_then_process_crashes(*args, **kwargs):
        summary = run_delayed_reconciliation(
            db_session,
            order_client=worker_client,
            now=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        assert summary.claimed_count == 1
        assert summary.retried_count == 1
        raise SystemExit("crash after premature worker lookup")

    monkeypatch.setattr(broker, "_submit_signed_order", worker_runs_then_process_crashes)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    db_session.rollback()
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 0
    assert len(worker_client.query_calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "created"
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert attempts[0].metadata_["automatic_reconciliation_last_resolution"] == "not_found"
    assert job is not None
    assert job.state == "pending"
    assert job.automatic_attempt_count == 1
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_premature_worker_not_found_can_exhaust_without_unblocking_submission(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    worker_client = RecordingOrderClient(
        query_response=BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"})
    )
    broker = guarded_testnet_broker(db_session, client)

    def worker_exhausts_then_process_crashes(*args, **kwargs):
        summary = run_delayed_reconciliation(
            db_session,
            order_client=worker_client,
            now=datetime.now(timezone.utc) + timedelta(minutes=10),
            max_attempts=1,
        )
        assert summary.claimed_count == 1
        assert summary.exhausted_count == 1
        raise SystemExit("crash after exhausted premature lookup")

    monkeypatch.setattr(broker, "_submit_signed_order", worker_exhausts_then_process_crashes)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    db_session.rollback()
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 0
    assert len(worker_client.query_calls) == 1
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert job is not None
    assert job.state == "exhausted"

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_worker_not_found_during_post_keeps_reservation_blocking(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    worker_client = RecordingOrderClient(
        query_response=BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"})
    )

    class WorkerDuringPostClient(RecordingOrderClient):
        def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
            self.calls.append(params)
            summary = run_delayed_reconciliation(
                db_session,
                order_client=worker_client,
                now=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
            assert summary.claimed_count == 1
            assert summary.retried_count == 1
            raise SystemExit("crash while post is in flight")

    client = WorkerDuringPostClient()
    broker = guarded_testnet_broker(db_session, client)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 1
    assert len(worker_client.query_calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "created"
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert job is not None
    assert job.state == "pending"
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_crash_after_reservation_before_post_leaves_blocking_reservation(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    def crash_before_post(*args, **kwargs):
        raise SystemExit("crash before post")

    monkeypatch.setattr(broker, "_submit_signed_order", crash_before_post)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 0
    assert len(attempts) == 1
    assert attempts[0].final_status == "created"
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert job is not None
    assert job.state == "pending"
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_crash_during_post_leaves_blocking_reservation(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")

    class CrashingOrderClient(RecordingOrderClient):
        def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
            self.calls.append(params)
            raise SystemExit("crash during post")

    client = CrashingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "created"
    assert attempts[0].metadata_["client_order_id"] == client.calls[0]["newClientOrderId"]
    assert job is not None
    assert job.state == "pending"
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


def test_binance_testnet_crash_after_post_response_before_final_update_leaves_blocking_reservation(
    db_session,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    def crash_before_final_update(*args, **kwargs):
        raise SystemExit("crash before final update")

    monkeypatch.setattr(broker, "_finalize_reserved_attempt", crash_before_final_update)

    with pytest.raises(SystemExit):
        broker.submit_market_order(
            BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
        )

    db_session.rollback()
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(client.calls) == 1
    assert len(attempts) == 1
    assert attempts[0].final_status == "created"
    assert attempts[0].metadata_["client_order_id"] == client.calls[0]["newClientOrderId"]
    assert job is not None
    assert job.state == "pending"
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.reason == "binance_testnet_unresolved_attempt_exists"
    assert next_client.calls == []


@pytest.mark.parametrize("job_state", ["none", "pending", "claimed", "exhausted"])
def test_binance_testnet_unresolved_persisted_attempt_blocks_second_real_submission_for_bot_scope(
    db_session,
    bot_stack_factory,
    job_state,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    unresolved = ExecutionAttemptService(ExecutionAttemptRepository(db_session)).record(
        bot_id=bot.id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=Decimal("0.1"),
        requested_price=Decimal("100"),
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status="rejected_by_broker",
        final_reason="testnet_order_reconciliation_unresolved",
        metadata={
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
        },
    )
    job_repository = ExecutionReconciliationJobRepository(db_session)
    if job_state != "none":
        job = job_repository.get_by_execution_attempt_id(unresolved.id)
        if job is None:
            job = job_repository.create_pending(
                execution_attempt_id=unresolved.id,
                bot_id=bot.id,
                next_attempt_at=FIXED_NOW,
            )
        if job_state == "claimed":
            job_repository.claim_due_jobs(now=FIXED_NOW, lease_seconds=60, limit=1)
        elif job_state == "exhausted":
            claimed = job_repository.claim_due_jobs(now=FIXED_NOW, lease_seconds=60, limit=1)[0]
            job_repository.mark_claimed_job_exhausted(
                job_id=claimed.id,
                lease_token=claimed.lease_token,
                checked_at=FIXED_NOW,
                resolution="not_found",
                failure_category=None,
            )
        db_session.commit()

    client = RecordingOrderClient()
    account_client = RecordingAccountClient()
    provider = StaticExchangeInfoProvider()
    broker = guarded_testnet_broker(db_session, client, account_client=account_client, exchange_info_provider=provider)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    assert result.accepted is False
    assert result.reason == "binance_testnet_unresolved_attempt_exists"
    assert result.metadata["guard_scope"] == "bot"
    assert result.metadata["unresolved_attempt_exists"] is True
    assert client.calls == []
    assert client.query_calls == []
    assert account_client.calls == []
    assert provider.calls == 0
    assert attempts[0].final_status == "blocked_by_safety"
    assert attempts[0].final_reason == "binance_testnet_unresolved_attempt_exists"
    assert "client_order_id" not in str(attempts[0].metadata_)
    assert "signature" not in str(attempts[0].metadata_).lower()


def test_binance_testnet_unresolved_attempt_from_previous_utc_day_still_blocks_real_submission(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    db_session.add(
        ExecutionAttempt(
            bot_id=bot.id,
            strategy_id=None,
            symbol="BTCUSDT",
            side="buy",
            mode="testnet",
            broker="binance_testnet",
            requested_quantity=Decimal("0.1"),
            requested_price=Decimal("100"),
            decision_reason=None,
            risk_status=None,
            safety_status="allowed",
            final_status="rejected_by_broker",
            final_reason="testnet_order_reconciliation_unresolved",
            metadata_={
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_resolution": "unresolved",
                "submission_recovered": False,
            },
            created_at=FIXED_NOW - timedelta(days=1),
        )
    )
    db_session.commit()
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    assert result.accepted is False
    assert result.reason == "binance_testnet_unresolved_attempt_exists"
    assert result.metadata["guard_scope"] == "bot"
    assert client.calls == []
    assert client.query_calls == []
    assert attempts[0].final_status == "blocked_by_safety"
    assert attempts[0].final_reason == "binance_testnet_unresolved_attempt_exists"
    assert attempts[1].created_at.date() == (FIXED_NOW - timedelta(days=1)).date()


def test_binance_testnet_resolved_known_outcome_allows_later_mocked_submission(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    ExecutionAttemptService(ExecutionAttemptRepository(db_session)).record(
        bot_id=bot.id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=Decimal("0.1"),
        requested_price=Decimal("100"),
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status="order_created",
        final_reason="testnet_order_recovered_after_unknown_submission",
        metadata={
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "found",
            "submission_recovered": True,
            "exchange_status": "FILLED",
        },
    )
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert result.reason is None
    assert len(client.calls) == 1


def test_binance_testnet_dry_run_allowed_with_unresolved_attempt_and_contacts_no_binance(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    ExecutionAttemptService(ExecutionAttemptRepository(db_session)).record(
        bot_id=bot.id,
        strategy_id=None,
        symbol="BTCUSDT",
        side="buy",
        mode="testnet",
        broker="binance_testnet",
        requested_quantity=Decimal("0.1"),
        requested_price=Decimal("100"),
        decision_reason=None,
        risk_status=None,
        safety_status="allowed",
        final_status="rejected_by_broker",
        final_reason="testnet_order_reconciliation_unresolved",
        metadata={
            "client_order_id": "tap_unresolved",
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
        },
    )

    class ExplodingAccountClient:
        calls = []

        def fetch_signed_account(self, params):
            self.calls.append(params)
            raise AssertionError("Dry-run must not contact Binance account endpoint")

    class ExplodingExchangeInfoProvider:
        calls = 0

        def get_exchange_info(self):
            self.calls += 1
            raise AssertionError("Dry-run must not contact Binance exchangeInfo endpoint")

    client = RecordingOrderClient()
    account_client = ExplodingAccountClient()
    provider = ExplodingExchangeInfoProvider()
    broker = guarded_testnet_broker(
        db_session,
        client,
        account_client=account_client,
        exchange_info_provider=provider,
        config=enabled_binance_config(dry_run_enabled=True),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "testnet_order_submission_dry_run"
    assert client.calls == []
    assert client.query_calls == []
    assert account_client.calls == []
    assert provider.calls == 0


def test_binance_testnet_broker_enabled_mocked_submission_normalizes_success(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient()
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

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
    assert result.metadata["exchange_order_id"] == "12345"
    assert result.metadata["client_order_id"] == client.calls[0]["newClientOrderId"]
    assert "signature" not in str(result.metadata).lower()
    assert "test-secret" not in str(result.metadata)
    assert len(attempts) == 1
    assert attempts[0].final_status == "order_created"
    assert "test-secret" not in str(attempts[0].metadata_)


def test_binance_testnet_broker_error_json_normalizes_rejection(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(
        response=BinanceOrderHttpResponse(
            status_code=400,
            payload={"code": -2010, "msg": "Account has insufficient balance"},
        )
    )
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is False
    assert result.reason == "binance_testnet_order_rejected"
    assert client.query_calls == []
    assert result.message == "Binance testnet order rejected: Account has insufficient balance"
    assert result.metadata["status_code"] == 400
    assert result.metadata["binance_code"] == -2010
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10)
    job = ExecutionReconciliationJobRepository(db_session).get_by_execution_attempt_id(attempts[0].id)
    assert len(attempts) == 1
    assert attempts[0].final_status == "rejected_by_broker"
    assert attempts[0].final_reason == "binance_testnet_order_rejected"
    assert job is not None
    assert job.state == "resolved"
    assert job.last_resolution == "known_rejected"
    assert quota_count(db_session, bot_id=bot.id) == 0

    next_client = RecordingOrderClient()
    next_result = guarded_testnet_broker(db_session, next_client).submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )
    assert next_result.accepted is True
    assert len(next_client.calls) == 1


def test_binance_testnet_broker_exchange_info_unavailable_blocks_before_signing_and_http(db_session) -> None:
    client = RecordingOrderClient()
    provider = StaticExchangeInfoProvider(exception=BinanceExchangeInfoError("raw unavailable detail"))
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        exchange_info_provider=provider,  # type: ignore[arg-type]
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.accepted is False
    assert result.reason == "testnet_exchange_info_unavailable"
    assert client.calls == []
    assert client.query_calls == []
    assert attempts[0].final_reason == "testnet_exchange_info_unavailable"
    assert "raw unavailable detail" not in str(attempts[0].metadata_)
    assert "signature" not in str(attempts[0].metadata_).lower()


def test_binance_testnet_broker_filter_rejection_blocks_before_signing_and_http(db_session) -> None:
    client = RecordingOrderClient()
    provider = StaticExchangeInfoProvider(
        BinanceExchangeInfo(
            symbols={
                "BTCUSDT": BinanceSymbolRules(
                    symbol="BTCUSDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    status="TRADING",
                    order_types=frozenset({"MARKET"}),
                )
            }
        )
    )
    # Attach a minimal lot-size filter after construction to keep this test focused on broker integration.
    rules = provider.info.symbols["BTCUSDT"]
    object.__setattr__(
        rules,
        "lot_size",
        BinanceQuantityFilter(
            filter_type="LOT_SIZE",
            min_qty=Decimal("1"),
            max_qty=Decimal("10"),
            step_size=Decimal("1"),
        ),
    )
    broker = BinanceTestnetBroker(
        enabled_binance_config(),
        http_client=client,
        exchange_info_provider=provider,  # type: ignore[arg-type]
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    result = broker.submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    attempts = ExecutionAttemptRepository(db_session).list_filtered()
    assert result.accepted is False
    assert result.reason == "testnet_quantity_below_minimum"
    assert client.calls == []
    assert client.query_calls == []
    assert attempts[0].metadata_["filter_type"] == "LOT_SIZE"
    assert "signature" not in str(attempts[0].metadata_).lower()


def test_binance_testnet_broker_non_2xx_without_error_message_normalizes_safely(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(response=BinanceOrderHttpResponse(status_code=500, payload={}))
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert result.reason == "testnet_order_recovered_after_unknown_submission"
    assert len(client.query_calls) == 1
    assert result.metadata["reconciliation_trigger"] == "http_5xx"
    assert result.metadata["reconciliation_resolution"] == "found"


def test_binance_testnet_broker_invalid_json_normalizes_safely(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(exception=BinanceInvalidOrderResponseError("Invalid JSON"))
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert result.reason == "testnet_order_recovered_after_unknown_submission"
    assert len(client.query_calls) == 1
    assert result.metadata["reconciliation_trigger"] == "invalid_success_response"


def test_binance_testnet_broker_network_error_normalizes_safely(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingOrderClient(exception=BinanceTestnetOrderClientError("timeout"))
    broker = guarded_testnet_broker(db_session, client)

    result = broker.submit_market_order(
        BrokerOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("0.1"), market_price=Decimal("100"))
    )

    assert result.accepted is True
    assert result.reason == "testnet_order_recovered_after_unknown_submission"
    assert len(client.query_calls) == 1
    assert result.metadata["reconciliation_trigger"] == "timeout"


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
    assert Settings.model_fields["binance_testnet_dry_run_enabled"].default is False
    assert Settings.model_fields["binance_testnet_exchange_info_ttl_seconds"].default == 300.0
