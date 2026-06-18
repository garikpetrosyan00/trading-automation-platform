from decimal import Decimal

import pytest

from app.core.config import Settings
from app.core.errors import ConflictError
from app.models.execution_attempt import ExecutionAttempt
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.schemas.execution import MarketOrderRequest
from app.models.simulated_fill import SimulatedFill
from app.services.brokers.base import BrokerOrderIntent
from app.services.draft_balance import DraftBalanceService
from app.services.execution_attempt import ExecutionAttemptService
from app.services.paper_portfolio import PaperPortfolioService
from app.services.paper_position import PaperPositionService
from app.services.portfolio import PortfolioService
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import PaperExecutionBroker, PaperExecutionService, PaperOrderIntent, SimulatedExecutionService


def build_fill(
    *,
    symbol: str = "BTCUSDT",
    side: str,
    quantity: Decimal,
    fill_price: Decimal,
    fee: Decimal = Decimal("0"),
) -> SimulatedFill:
    return SimulatedFill(
        order_id=1,
        symbol=symbol,
        side=side,
        quantity=quantity,
        fill_quantity=quantity,
        fill_price=fill_price,
        fee=fee,
        source="paper",
    )


def build_draft_balance_service(session) -> DraftBalanceService:
    return DraftBalanceService(DraftBalanceRepository(session), BotRepository(session))


def build_paper_position_service(session) -> PaperPositionService:
    return PaperPositionService(PaperPositionRepository(session))


def draft_assets_by_symbol(session, bot_id: int):
    snapshot = build_draft_balance_service(session).get_bot_draft_balance(bot_id)
    return {asset.asset: asset for asset in snapshot.assets}


def test_account_bootstrap_creates_default_account(db_session) -> None:
    service = PortfolioAccountService(PortfolioRepository(db_session))

    account = service.ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))

    assert account.base_currency == "USD"
    assert account.starting_cash == Decimal("1000.00")
    assert account.cash_balance == Decimal("1000.00")


def test_settings_default_paper_initial_balance_is_positive(monkeypatch) -> None:
    monkeypatch.delenv("PAPER_INITIAL_BALANCE", raising=False)
    monkeypatch.delenv("SIMULATION_STARTING_CASH", raising=False)
    settings = Settings(_env_file=None)

    assert settings.paper_initial_balance == Decimal("10000.00")


def test_settings_rejects_non_positive_paper_initial_balance() -> None:
    with pytest.raises(ValueError):
        Settings(PAPER_INITIAL_BALANCE="0")


def test_paper_portfolio_buy_fill_updates_position_and_average_entry(db_session) -> None:
    repository = PortfolioRepository(db_session)
    account = PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    fill = build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100"), fee=Decimal("1"))

    result = PaperPortfolioService(repository).apply_fill(fill)

    position = repository.get_position_by_symbol("BTCUSDT")
    assert result.accepted is True
    assert position is not None
    assert position.quantity == Decimal("2")
    assert position.average_entry_price == Decimal("100.5")
    assert position.realized_pnl == Decimal("0")
    assert account.cash_balance == Decimal("799.00")


def test_paper_portfolio_multiple_buy_fills_update_weighted_average_entry(db_session) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperPortfolioService(repository)

    first = service.apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))
    second = service.apply_fill(build_fill(side="buy", quantity=Decimal("1"), fill_price=Decimal("130")))

    position = repository.get_position_by_symbol("BTCUSDT")
    assert first.accepted is True
    assert second.accepted is True
    assert position is not None
    assert position.quantity == Decimal("3")
    assert position.average_entry_price == Decimal("110")


def test_paper_portfolio_sell_fill_reduces_position_and_calculates_realized_pnl(db_session) -> None:
    repository = PortfolioRepository(db_session)
    account = PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperPortfolioService(repository)
    service.apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))

    result = service.apply_fill(build_fill(side="sell", quantity=Decimal("2"), fill_price=Decimal("125"), fee=Decimal("1")))

    position = repository.get_position_by_symbol("BTCUSDT")
    assert result.accepted is True
    assert result.realized_pnl_delta == Decimal("49")
    assert position is not None
    assert position.quantity == Decimal("0")
    assert position.average_entry_price == Decimal("0")
    assert position.realized_pnl == Decimal("49")
    assert account.cash_balance == Decimal("1049.00")


def test_paper_portfolio_partial_sell_keeps_remaining_average_entry(db_session) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperPortfolioService(repository)
    service.apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))

    result = service.apply_fill(build_fill(side="sell", quantity=Decimal("0.75"), fill_price=Decimal("120")))

    position = repository.get_position_by_symbol("BTCUSDT")
    assert result.accepted is True
    assert position is not None
    assert position.quantity == Decimal("1.25")
    assert position.average_entry_price == Decimal("100")
    assert position.realized_pnl == Decimal("15.00")


def test_paper_portfolio_oversell_is_rejected_without_state_change(db_session) -> None:
    repository = PortfolioRepository(db_session)
    account = PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperPortfolioService(repository)
    service.apply_fill(build_fill(side="buy", quantity=Decimal("1"), fill_price=Decimal("100")))

    result = service.apply_fill(build_fill(side="sell", quantity=Decimal("2"), fill_price=Decimal("120")))

    position = repository.get_position_by_symbol("BTCUSDT")
    assert result.accepted is False
    assert result.message == "Insufficient position quantity for this sell order"
    assert position is not None
    assert position.quantity == Decimal("1")
    assert position.realized_pnl == Decimal("0")
    assert account.cash_balance == Decimal("900.00")


def test_paper_portfolio_invalid_fill_does_not_corrupt_state(db_session) -> None:
    repository = PortfolioRepository(db_session)
    account = PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = PaperPortfolioService(repository)

    zero_quantity = service.apply_fill(build_fill(side="buy", quantity=Decimal("0"), fill_price=Decimal("100")))
    invalid_price = service.apply_fill(build_fill(side="buy", quantity=Decimal("1"), fill_price=Decimal("0")))

    assert zero_quantity.accepted is False
    assert zero_quantity.message == "Fill quantity must be a positive number"
    assert invalid_price.accepted is False
    assert invalid_price.message == "Fill price must be a positive number"
    assert repository.get_position_by_symbol("BTCUSDT") is None
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
    assert result.order.order_type == "market"
    assert result.order.mode == "paper"
    assert result.fill.fill_quantity == result.order.quantity
    assert result.fill.source == "paper"
    events = PaperAccountingRepository(db_session).list_events()
    assert len(events) == 1
    assert events[0].order_id == result.order.id
    assert events[0].fill_id == result.fill.id
    assert events[0].cash_delta == Decimal("-500.75025000")
    assert events[0].realized_pnl_delta == Decimal("0E-8")


def test_paper_execution_applies_fills_through_portfolio_service(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    calls = {"count": 0}
    original_apply_fill = PaperPortfolioService.apply_fill

    def counting_apply_fill(self, fill):
        calls["count"] += 1
        return original_apply_fill(self, fill)

    monkeypatch.setattr(PaperPortfolioService, "apply_fill", counting_apply_fill)
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(PaperOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    position = repository.get_position_by_symbol("BTCUSDT")
    assert result.accepted is True
    assert calls["count"] == 1
    assert result.fill is not None
    assert position is not None
    assert position.quantity == Decimal("1.00000000")
    assert position.average_entry_price == Decimal("100.00000000")


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
    assert result.message == "insufficient_paper_cash"
    assert result.fill is None
    assert result.updated_cash_balance == Decimal("1000.00000000")
    assert result.order.status == "rejected"
    assert result.order.rejection_reason == "insufficient_paper_cash"
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert repository.get_account().cash_balance == Decimal("1000.00000000")


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
    events = PaperAccountingRepository(db_session).list_events()
    assert len(events) == 2
    assert events[0].fill_id == result.fill.id
    assert events[0].cash_delta == Decimal("203.69410200")
    assert events[0].realized_pnl_delta == Decimal("3.39400200")


def test_paper_buy_updates_selected_bot_draft_balance(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    build_draft_balance_service(db_session).reset_bot_draft_balance(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("2"))
    )

    assets = draft_assets_by_symbol(db_session, bot.id)
    assert result.accepted is True
    assert assets["USDT"].available == Decimal("9799.80000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["USDT"].total == Decimal("9799.80000000")
    assert assets["BTC"].available == Decimal("2.00000000")
    assert assets["BTC"].locked == Decimal("0E-8")
    assert assets["BTC"].total == Decimal("2.00000000")


def test_paper_sell_updates_selected_bot_draft_balance(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    PaperPortfolioService(repository).apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))
    db_session.commit()
    build_paper_position_service(db_session).apply_buy_fill(
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("2"),
        fill_price=Decimal("100"),
    )
    build_draft_balance_service(db_session).reset_bot_draft_balance(
        bot.id,
        defaults={
            "BTC": (Decimal("2"), Decimal("0")),
            "USDT": (Decimal("10000"), Decimal("0")),
        },
    )
    stub_market_data_service.set_price("BTCUSDT", "110.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("10"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="sell", quantity=Decimal("0.5"))
    )

    assets = draft_assets_by_symbol(db_session, bot.id)
    assert result.accepted is True
    assert assets["BTC"].available == Decimal("1.50000000")
    assert assets["BTC"].locked == Decimal("0E-8")
    assert assets["BTC"].total == Decimal("1.50000000")
    assert assets["USDT"].available == Decimal("10054.94500000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["USDT"].total == Decimal("10054.94500000")


def test_paper_buy_rejects_insufficient_draft_quote_without_paper_mutation(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    build_draft_balance_service(db_session).reset_bot_draft_balance(
        bot.id,
        defaults={"USDT": (Decimal("10"), Decimal("0"))},
    )
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assets = draft_assets_by_symbol(db_session, bot.id)
    assert result.accepted is False
    assert result.order is None
    assert result.fill is None
    assert result.message == "insufficient_draft_balance_available"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert assets["USDT"].available == Decimal("10.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")


def test_paper_sell_rejects_insufficient_draft_base_without_paper_mutation(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    PaperPortfolioService(repository).apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))
    db_session.commit()
    build_draft_balance_service(db_session).reset_bot_draft_balance(
        bot.id,
        defaults={"BTC": (Decimal("0.25"), Decimal("0"))},
    )
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="sell", quantity=Decimal("1"))
    )

    assets = draft_assets_by_symbol(db_session, bot.id)
    assert result.accepted is False
    assert result.order is None
    assert result.fill is None
    assert result.message == "insufficient_draft_balance_available"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT").quantity == Decimal("2.00000000")
    assert assets["BTC"].available == Decimal("0.25000000")
    assert assets["BTC"].locked == Decimal("0E-8")


def test_paper_accounting_failure_releases_draft_reservation(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    build_draft_balance_service(db_session).reset_bot_draft_balance(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    def fail_accounting_event(self, *, fill, cash_delta, realized_pnl_delta):
        raise RuntimeError("forced accounting failure")

    monkeypatch.setattr(PaperPortfolioService, "_record_accounting_event", fail_accounting_event)

    with pytest.raises(RuntimeError, match="forced accounting failure"):
        service.submit_order_intent(
            PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
        )

    assets = draft_assets_by_symbol(db_session, bot.id)
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert PaperAccountingRepository(db_session).list_events() == []
    assert assets["USDT"].available == Decimal("10000.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["BTC"].available == Decimal("0E-8")


def test_draft_balance_mutation_is_scoped_to_selected_bot(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    _, other_bot, _ = bot_stack_factory(db_session, name="Other Bot")
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    draft_service = build_draft_balance_service(db_session)
    draft_service.reset_bot_draft_balance(bot.id)
    draft_service.reset_bot_draft_balance(
        other_bot.id,
        defaults={"USDT": (Decimal("500"), Decimal("0")), "BTC": (Decimal("3"), Decimal("0"))},
    )
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    selected_assets = draft_assets_by_symbol(db_session, bot.id)
    other_assets = draft_assets_by_symbol(db_session, other_bot.id)
    assert result.accepted is True
    assert selected_assets["USDT"].available == Decimal("9900.00000000")
    assert selected_assets["BTC"].available == Decimal("1.00000000")
    assert other_assets["USDT"].available == Decimal("500.00000000")
    assert other_assets["BTC"].available == Decimal("3.00000000")


def test_accounting_failure_rolls_back_order_fill_cash_position_and_event(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    def fail_accounting_event(self, *, fill, cash_delta, realized_pnl_delta):
        raise RuntimeError("forced accounting failure")

    monkeypatch.setattr(PaperPortfolioService, "_record_accounting_event", fail_accounting_event)

    with pytest.raises(RuntimeError, match="forced accounting failure"):
        service.submit_market_order(MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    account = repository.get_account()
    assert account.cash_balance == Decimal("1000.00000000")
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert PaperAccountingRepository(db_session).list_events() == []


def test_accounting_failure_rolls_back_reserved_execution_attempt(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(db_session)),
    )

    def fail_accounting_event(self, *, fill, cash_delta, realized_pnl_delta):
        raise RuntimeError("forced accounting failure")

    monkeypatch.setattr(PaperPortfolioService, "_record_accounting_event", fail_accounting_event)

    with pytest.raises(RuntimeError, match="forced accounting failure"):
        service.submit_market_order(MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert ExecutionAttemptRepository(db_session).list_filtered() == []


def test_duplicate_fill_accounting_is_rejected_without_second_mutation(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    result = service.submit_market_order(MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    assert result.fill is not None
    cash_after_first = repository.get_account().cash_balance
    quantity_after_first = repository.get_position_by_symbol("BTCUSDT").quantity

    duplicate = PaperPortfolioService(repository).apply_fill(result.fill)

    assert duplicate.accepted is False
    assert duplicate.message == "duplicate_fill_accounting"
    assert repository.get_account().cash_balance == cash_after_first
    assert repository.get_position_by_symbol("BTCUSDT").quantity == quantity_after_first
    assert len(PaperAccountingRepository(db_session).list_events()) == 1


def test_paper_execution_uses_locked_account_mutation_path(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100.00")
    calls = {"count": 0}
    original = repository.get_account_for_update

    def counting_get_account_for_update():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(repository, "get_account_for_update", counting_get_account_for_update)
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_market_order(MarketOrderRequest(symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is True
    assert calls["count"] >= 2


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


def test_missing_market_price_rejects_without_fill(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(PaperOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0.01")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.fill is None
    assert result.order.rejection_reason == "No latest market price available for symbol BTCUSDT"
    assert repository.list_fills() == []


def test_invalid_quantity_rejects_without_fill(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(PaperOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("0")))

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.fill is None
    assert result.order.status == "rejected"
    assert result.order.rejection_reason == "Order quantity must be a positive number"
    assert repository.list_fills() == []


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


def test_paper_execution_broker_records_insufficient_cash_attempt(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("100.00"))
    stub_market_data_service.set_price("BTCUSDT", "50000.00")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    attempt_service = ExecutionAttemptService(ExecutionAttemptRepository(db_session))

    result = PaperExecutionBroker(service, attempt_service=attempt_service).submit_market_order(
        BrokerOrderIntent(bot_id=1, strategy_id=2, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    attempts = db_session.query(ExecutionAttempt).all()
    assert result.accepted is False
    assert result.reason == "insufficient_paper_cash"
    assert len(attempts) == 1
    assert attempts[0].final_status == "rejected_by_broker"
    assert attempts[0].final_reason == "insufficient_paper_cash"
    assert attempts[0].safety_status == "allowed"
    assert attempts[0].order_id == result.order_id


def test_paper_snapshot_returns_nullable_market_values_when_price_missing(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    PaperPortfolioService(repository).apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))
    db_session.commit()

    snapshot = PortfolioService(repository, stub_market_data_service).get_paper_snapshot()

    assert snapshot.starting_balance == Decimal("1000.00000000")
    assert snapshot.cash_balance == Decimal("800.00000000")
    assert snapshot.positions_market_value == Decimal("0")
    assert snapshot.total_equity == Decimal("800.00000000")
    assert snapshot.total_market_value == Decimal("0")
    assert snapshot.total_unrealized_pnl == Decimal("0")
    assert snapshot.positions[0].symbol == "BTCUSDT"
    assert snapshot.positions[0].quantity == Decimal("2.00000000")
    assert snapshot.positions[0].average_entry_price == Decimal("100.00000000")
    assert snapshot.positions[0].latest_price is None
    assert snapshot.positions[0].latest_market_price is None
    assert snapshot.positions[0].market_value is None
    assert snapshot.positions[0].unrealized_pnl is None
    assert snapshot.positions[0].unrealized_pnl_percent is None
    assert snapshot.positions[0].price_available is False


def test_paper_snapshot_returns_equity_when_prices_are_available(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    PaperPortfolioService(repository).apply_fill(build_fill(side="buy", quantity=Decimal("2"), fill_price=Decimal("100")))
    db_session.commit()
    stub_market_data_service.set_price("BTCUSDT", "125")

    snapshot = PortfolioService(repository, stub_market_data_service).get_paper_snapshot()

    assert snapshot.starting_balance == Decimal("1000.00000000")
    assert snapshot.cash_balance == Decimal("800.00000000")
    assert snapshot.positions_market_value == Decimal("250.00000000")
    assert snapshot.total_market_value == Decimal("250.00000000")
    assert snapshot.total_unrealized_pnl == Decimal("50.00000000")
    assert snapshot.total_equity == Decimal("1050.00000000")


def test_paper_reset_rejects_invalid_balance(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))

    with pytest.raises(ValueError):
        PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("0"))


def test_paper_reset_rejects_when_open_position_exists(db_session, stub_market_data_service) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    PaperPortfolioService(repository).apply_fill(build_fill(side="buy", quantity=Decimal("1"), fill_price=Decimal("100")))
    db_session.commit()

    with pytest.raises(ConflictError):
        PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("5000"))

    assert repository.get_account().cash_balance == Decimal("900.00000000")


def test_paper_reset_uses_locked_account_mutation_path(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    calls = {"count": 0}
    original = repository.get_account_for_update

    def counting_get_account_for_update():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(repository, "get_account_for_update", counting_get_account_for_update)

    reset = PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("2500.00"))

    assert reset.cash_balance == Decimal("2500.00000000")
    assert calls["count"] == 1


def test_paper_reset_succeeds_when_flat_and_preserves_audit_history(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    execution_service = SimulatedExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    attempt_service = ExecutionAttemptService(ExecutionAttemptRepository(db_session))
    stub_market_data_service.set_price("BTCUSDT", "100")
    PaperExecutionBroker(execution_service, attempt_service=attempt_service).submit_market_order(
        BrokerOrderIntent(bot_id=1, strategy_id=2, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )
    stub_market_data_service.set_price("BTCUSDT", "120")
    PaperExecutionBroker(execution_service, attempt_service=attempt_service).submit_market_order(
        BrokerOrderIntent(bot_id=1, strategy_id=2, symbol="BTCUSDT", side="sell", quantity=Decimal("1"))
    )

    reset = PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("5000.00"))

    account = repository.get_account()
    position = repository.get_position_by_symbol("BTCUSDT")
    assert reset.starting_balance == Decimal("5000.00000000")
    assert reset.cash_balance == Decimal("5000.00000000")
    assert account.starting_cash == Decimal("5000.00000000")
    assert account.cash_balance == Decimal("5000.00000000")
    assert position is not None
    assert position.quantity == Decimal("0E-8")
    assert position.realized_pnl == Decimal("0")
    assert len(repository.list_orders()) == 2
    assert len(repository.list_fills()) == 2
    assert len(PaperAccountingRepository(db_session).list_events()) == 2
    assert len(db_session.query(ExecutionAttempt).all()) == 2


def test_paper_execution_rejects_live_mode_without_mutating_paper_state(
    db_session,
    stub_market_data_service,
) -> None:
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = service.submit_order_intent(
        PaperOrderIntent(symbol="BTCUSDT", side="buy", quantity=Decimal("1"), mode="live")
    )

    assert result.accepted is False
    assert result.order.mode == "live"
    assert result.fill is None
    assert repository.get_account().cash_balance == Decimal("1000.00000000")
    assert repository.get_position_by_symbol("BTCUSDT") is None
