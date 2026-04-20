from decimal import Decimal

from app.repositories.portfolio import PortfolioRepository
from app.schemas.execution import MarketOrderRequest
from app.services.portfolio import PortfolioService
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import SimulatedExecutionService


def test_account_bootstrap_creates_default_account(db_session) -> None:
    service = PortfolioAccountService(PortfolioRepository(db_session))

    account = service.ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))

    assert account.base_currency == "USD"
    assert account.starting_cash == Decimal("1000.00")
    assert account.cash_balance == Decimal("1000.00")


def test_successful_buy_updates_account_and_position(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    result = service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("0.01"))
    )

    assert result.accepted is True
    assert result.status == "filled"
    assert result.fill is not None
    assert result.fill.fill_price == Decimal("50025.000000")
    assert result.fill.fee == Decimal("0.5002500000000")
    assert result.updated_cash_balance == Decimal("499.24975000")
    assert result.position is not None
    assert result.position.quantity == Decimal("0.01000000")
    assert result.position.average_entry_price == Decimal("50075.025000")


def test_rejected_buy_due_to_insufficient_cash(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    result = service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.message == "Insufficient cash balance for this buy order"
    assert result.fill is None
    assert result.updated_cash_balance == Decimal("1000.00000000")


def test_successful_sell_updates_realized_pnl(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    execution_service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    execution_service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("0.01"))
    )
    stub_market_data_service.set_price("BTCUSDT", "51000.00")

    result = execution_service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="sell", quantity=Decimal("0.004"))
    )

    assert result.accepted is True
    assert result.fill is not None
    assert result.fill.fill_price == Decimal("50974.500000")
    assert result.fill.fee == Decimal("0.2038980000000")
    assert result.updated_cash_balance == Decimal("702.94385200")
    assert result.position is not None
    assert result.position.quantity == Decimal("0.00600000")
    assert result.position.realized_pnl == Decimal("3.39400200")


def test_rejected_sell_due_to_insufficient_quantity(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    result = service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="sell", quantity=Decimal("0.01"))
    )

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.message == "Insufficient position quantity for this sell order"


def test_portfolio_summary_uses_latest_market_price(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    execution_service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
    )

    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    execution_service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("0.01"))
    )
    stub_market_data_service.set_price("BTCUSDT", "51000.00")
    execution_service.submit_market_order(
        MarketOrderRequest(symbol="BTCUSDT", side="sell", quantity=Decimal("0.004"))
    )

    summary = PortfolioService(repository, stub_market_data_service).get_summary()

    assert summary.cash_balance == Decimal("702.94385200")
    assert summary.market_value == Decimal("306.00000000")
    assert summary.equity == Decimal("1008.94385200")
    assert summary.unrealized_pnl == Decimal("5.54985000")
    assert summary.realized_pnl == Decimal("3.39400200")
