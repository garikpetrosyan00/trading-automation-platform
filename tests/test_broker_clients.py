import asyncio
from decimal import Decimal

from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.base import BrokerOrderIntent
from app.services.brokers.binance import BinanceTestnetBroker, BinanceTestnetBrokerConfig
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.core.config import Settings
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import PaperExecutionBroker, PaperExecutionService


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

    result = PaperExecutionBroker(service, safety_guard=guard).submit_market_order(
        BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assert result.accepted is False
    assert result.reason == "execution_global_disabled"
    assert repository.list_orders() == []
    assert repository.list_fills() == []


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


def test_binance_testnet_broker_missing_credentials_rejects_safely() -> None:
    broker = BinanceTestnetBroker(
        BinanceTestnetBrokerConfig(
            enabled=True,
            order_submission_enabled=True,
            api_key=None,
            api_secret=None,
        )
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="sell", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "missing_testnet_credentials"
    assert result.message == "Binance testnet API credentials are not configured"


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
        BinanceTestnetBrokerConfig(
            enabled=True,
            order_submission_enabled=True,
            api_key="test-key",
            api_secret="test-secret",
        )
    )

    result = broker.submit_market_order(BrokerOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.1")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.reason == "testnet_order_submission_not_implemented"


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
