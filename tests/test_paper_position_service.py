from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.models.paper_position import PaperPosition
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.draft_balance import DraftBalanceService
from app.services.paper_position import PaperPositionService
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import PaperExecutionService, PaperOrderIntent


def build_service(session, *, autocommit: bool = True) -> PaperPositionService:
    return PaperPositionService(PaperPositionRepository(session), autocommit=autocommit)


def apply_buy(
    service: PaperPositionService,
    *,
    bot_id: int,
    quantity: str,
    fill_price: str,
    fee: str = "0",
) -> PaperPosition:
    return service.apply_buy_fill(
        bot_id=bot_id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal(quantity),
        fill_price=Decimal(fill_price),
        fee=Decimal(fee),
    )


def apply_sell(
    service: PaperPositionService,
    *,
    bot_id: int,
    quantity: str,
    fill_price: str,
    fee: str = "0",
) -> PaperPosition:
    return service.apply_sell_fill(
        bot_id=bot_id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal(quantity),
        fill_price=Decimal(fill_price),
        fee=Decimal(fee),
    )


def test_first_buy_opens_paper_position(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)

    position = apply_buy(
        build_service(db_session),
        bot_id=bot.id,
        quantity="2",
        fill_price="100",
        fee="1",
    )

    assert position.bot_id == bot.id
    assert position.symbol == "BTCUSDT"
    assert position.base_asset == "BTC"
    assert position.quote_asset == "USDT"
    assert position.quantity == Decimal("2.00000000")
    assert position.average_entry_price == Decimal("100.50000000")
    assert position.realized_pnl == Decimal("0E-8")


def test_second_buy_updates_weighted_average_entry(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = build_service(db_session)
    apply_buy(service, bot_id=bot.id, quantity="2", fill_price="100")

    position = apply_buy(service, bot_id=bot.id, quantity="1", fill_price="130")

    assert position.quantity == Decimal("3.00000000")
    assert position.average_entry_price == Decimal("110.00000000")
    assert position.realized_pnl == Decimal("0E-8")


def test_partial_sell_updates_quantity_and_realized_pnl(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = build_service(db_session)
    apply_buy(service, bot_id=bot.id, quantity="2", fill_price="100")

    position = apply_sell(
        service,
        bot_id=bot.id,
        quantity="0.75",
        fill_price="120",
        fee="1",
    )

    assert position.quantity == Decimal("1.25000000")
    assert position.average_entry_price == Decimal("100.00000000")
    assert position.realized_pnl == Decimal("14.00000000")


def test_full_sell_closes_position_and_preserves_realized_pnl(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = build_service(db_session)
    apply_buy(service, bot_id=bot.id, quantity="2", fill_price="100")
    apply_sell(service, bot_id=bot.id, quantity="0.5", fill_price="120")

    position = apply_sell(service, bot_id=bot.id, quantity="1.5", fill_price="110")

    assert position.quantity == Decimal("0E-8")
    assert position.average_entry_price == Decimal("0E-8")
    assert position.realized_pnl == Decimal("25.00000000")


def test_sell_greater_than_position_is_rejected_without_mutation(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = build_service(db_session)
    apply_buy(service, bot_id=bot.id, quantity="1", fill_price="100")

    with pytest.raises(AppError) as exc_info:
        apply_sell(service, bot_id=bot.id, quantity="2", fill_price="120")

    position = service.get_current_position(bot_id=bot.id, symbol="BTCUSDT")
    assert exc_info.value.error_code == "insufficient_paper_position_quantity"
    assert position is not None
    assert position.quantity == Decimal("1.00000000")
    assert position.average_entry_price == Decimal("100.00000000")
    assert position.realized_pnl == Decimal("0E-8")


def test_another_bots_position_is_unaffected(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    _, other_bot, _ = bot_stack_factory(db_session, name="Other Bot")
    service = build_service(db_session)
    apply_buy(service, bot_id=bot.id, quantity="2", fill_price="100")
    apply_buy(service, bot_id=other_bot.id, quantity="3", fill_price="50")

    apply_sell(service, bot_id=bot.id, quantity="1", fill_price="120")

    selected = service.get_current_position(bot_id=bot.id, symbol="BTCUSDT")
    other = service.get_current_position(bot_id=other_bot.id, symbol="BTCUSDT")
    assert selected is not None
    assert selected.quantity == Decimal("1.00000000")
    assert selected.realized_pnl == Decimal("20.00000000")
    assert other is not None
    assert other.quantity == Decimal("3.00000000")
    assert other.average_entry_price == Decimal("50.00000000")
    assert other.realized_pnl == Decimal("0E-8")


def test_successful_bot_paper_fill_updates_position_with_order_fill_and_draft_balance(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000"))
    DraftBalanceService(DraftBalanceRepository(db_session), BotRepository(db_session)).reset_bot_draft_balance(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    execution_service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    result = execution_service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    position = build_service(db_session).get_current_position(bot_id=bot.id, symbol="BTCUSDT")
    assert result.accepted is True
    assert result.order is not None
    assert result.fill is not None
    assert position is not None
    assert position.quantity == Decimal("1.00000000")
    assert position.average_entry_price == Decimal("100.00000000")


def test_paper_position_failure_rolls_back_order_fill_portfolio_and_draft_balance(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    repository = PortfolioRepository(db_session)
    account = PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000"))
    draft_service = DraftBalanceService(DraftBalanceRepository(db_session), BotRepository(db_session))
    draft_service.reset_bot_draft_balance(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    execution_service = PaperExecutionService(
        repository=repository,
        market_data_service=stub_market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    def fail_position_update(self, **kwargs):
        raise RuntimeError("forced paper position failure")

    monkeypatch.setattr(PaperPositionService, "apply_buy_fill", fail_position_update)

    with pytest.raises(RuntimeError, match="forced paper position failure"):
        execution_service.submit_order_intent(
            PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
        )

    assets = {asset.asset: asset for asset in draft_service.get_bot_draft_balance(bot.id).assets}
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert build_service(db_session).get_current_position(bot_id=bot.id, symbol="BTCUSDT") is None
    assert account.cash_balance == Decimal("1000.00000000")
    assert assets["USDT"].available == Decimal("10000.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["BTC"].available == Decimal("0E-8")
