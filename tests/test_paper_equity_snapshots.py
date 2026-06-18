from decimal import Decimal

import pytest

from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.draft_balance import DraftBalanceService
from app.services.paper_equity_snapshot import PaperEquitySnapshotService
from app.services.paper_position import PaperPositionService
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import PaperExecutionService, PaperOrderIntent


def build_execution_service(session, market_data_service, *, fee_bps: str = "10") -> PaperExecutionService:
    repository = PortfolioRepository(session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000"))
    return PaperExecutionService(
        repository=repository,
        market_data_service=market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal(fee_bps),
        slippage_bps=Decimal("0"),
    )


def reset_draft_balance(
    session,
    *,
    bot_id: int,
    defaults: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> None:
    DraftBalanceService(DraftBalanceRepository(session), BotRepository(session)).reset_bot_draft_balance(
        bot_id,
        defaults=defaults,
    )


def snapshots_for_bot(session, bot_id: int):
    return PaperEquitySnapshotRepository(session).list_latest_for_bot(bot_id=bot_id)


def test_buy_fill_creates_equity_snapshot_matching_post_fill_state(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot_id=bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = build_execution_service(db_session, stub_market_data_service)

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("2"))
    )

    snapshots = snapshots_for_bot(db_session, bot.id)
    assert result.accepted is True
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.event_type == "buy_fill"
    assert snapshot.source_order_id == result.order.id
    assert snapshot.source_fill_id == result.fill.id
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.quote_asset == "USDT"
    assert snapshot.cash_available == Decimal("9799.80000000")
    assert snapshot.cash_locked == Decimal("0E-8")
    assert snapshot.base_quantity == Decimal("2.00000000")
    assert snapshot.base_locked == Decimal("0E-8")
    assert snapshot.average_entry_price == Decimal("100.10000000")
    assert snapshot.realized_pnl == Decimal("0E-8")
    assert snapshot.market_price == Decimal("100.00000000")
    assert snapshot.position_value == Decimal("200.00000000")
    assert snapshot.total_equity == Decimal("9999.80000000")


def test_sell_fill_creates_snapshot_with_realized_pnl_and_current_equity(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot_id=bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = build_execution_service(db_session, stub_market_data_service)
    service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("2"))
    )
    stub_market_data_service.set_price("BTCUSDT", "120")

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="sell", quantity=Decimal("1"))
    )

    snapshots = snapshots_for_bot(db_session, bot.id)
    assert result.accepted is True
    assert len(snapshots) == 2
    sell_snapshot = snapshots[0]
    assert sell_snapshot.event_type == "sell_fill"
    assert sell_snapshot.source_order_id == result.order.id
    assert sell_snapshot.source_fill_id == result.fill.id
    assert sell_snapshot.cash_available == Decimal("9919.68000000")
    assert sell_snapshot.cash_locked == Decimal("0E-8")
    assert sell_snapshot.base_quantity == Decimal("1.00000000")
    assert sell_snapshot.base_locked == Decimal("0E-8")
    assert sell_snapshot.average_entry_price == Decimal("100.10000000")
    assert sell_snapshot.realized_pnl == Decimal("19.78000000")
    assert sell_snapshot.market_price == Decimal("120.00000000")
    assert sell_snapshot.position_value == Decimal("120.00000000")
    assert sell_snapshot.total_equity == Decimal("10039.68000000")


def test_missing_local_price_keeps_open_position_valuation_unknown(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(
        db_session,
        bot_id=bot.id,
        defaults={
            "BTC": (Decimal("1"), Decimal("0.25")),
            "USDT": (Decimal("500"), Decimal("25")),
        },
    )
    PaperPositionService(PaperPositionRepository(db_session)).apply_buy_fill(
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=Decimal("1.25"),
        fill_price=Decimal("100"),
    )
    service = PaperEquitySnapshotService(
        PaperEquitySnapshotRepository(db_session),
        DraftBalanceRepository(db_session),
        PaperPositionRepository(db_session),
    )

    snapshot = service.create_snapshot(
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        event_type="manual_snapshot",
    )
    db_session.commit()

    assert snapshot.market_price is None
    assert snapshot.position_value is None
    assert snapshot.total_equity is None
    assert snapshot.cash_available == Decimal("500.00000000")
    assert snapshot.cash_locked == Decimal("25.00000000")
    assert snapshot.base_quantity == Decimal("1.00000000")
    assert snapshot.base_locked == Decimal("0.25000000")


def test_missing_local_price_keeps_flat_cash_equity_exact(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(
        db_session,
        bot_id=bot.id,
        defaults={"USDT": (Decimal("500"), Decimal("25"))},
    )
    service = PaperEquitySnapshotService(
        PaperEquitySnapshotRepository(db_session),
        DraftBalanceRepository(db_session),
        PaperPositionRepository(db_session),
    )

    snapshot = service.create_snapshot(
        bot_id=bot.id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        event_type="manual_snapshot",
    )
    db_session.commit()

    assert snapshot.market_price is None
    assert snapshot.position_value is None
    assert snapshot.total_equity == Decimal("525.00000000")


def test_snapshots_are_isolated_by_bot(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    _, other_bot, _ = bot_stack_factory(db_session, name="Other Bot")
    reset_draft_balance(db_session, bot_id=bot.id)
    reset_draft_balance(db_session, bot_id=other_bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = build_execution_service(db_session, stub_market_data_service, fee_bps="0")

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assert result.accepted is True
    assert len(snapshots_for_bot(db_session, bot.id)) == 1
    assert snapshots_for_bot(db_session, other_bot.id) == []


def test_rejected_paper_execution_does_not_create_snapshot(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(
        db_session,
        bot_id=bot.id,
        defaults={"USDT": (Decimal("10"), Decimal("0"))},
    )
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = build_execution_service(db_session, stub_market_data_service, fee_bps="0")

    result = service.submit_order_intent(
        PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
    )

    assert result.accepted is False
    assert result.message == "insufficient_draft_balance_available"
    assert snapshots_for_bot(db_session, bot.id) == []


def test_snapshot_failure_rolls_back_order_fill_balances_and_position(
    db_session,
    stub_market_data_service,
    bot_stack_factory,
    monkeypatch,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    reset_draft_balance(db_session, bot_id=bot.id)
    stub_market_data_service.set_price("BTCUSDT", "100")
    service = build_execution_service(db_session, stub_market_data_service, fee_bps="0")

    def fail_snapshot(self, **kwargs):
        raise RuntimeError("forced equity snapshot failure")

    monkeypatch.setattr(PaperEquitySnapshotService, "create_snapshot", fail_snapshot)

    with pytest.raises(RuntimeError, match="forced equity snapshot failure"):
        service.submit_order_intent(
            PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
        )

    draft = DraftBalanceService(
        DraftBalanceRepository(db_session),
        BotRepository(db_session),
    ).get_bot_draft_balance(bot.id)
    assets = {asset.asset: asset for asset in draft.assets}
    repository = PortfolioRepository(db_session)
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_position_by_symbol("BTCUSDT") is None
    assert PaperPositionRepository(db_session).get_for_bot_symbol(bot_id=bot.id, symbol="BTCUSDT") is None
    assert snapshots_for_bot(db_session, bot.id) == []
    assert assets["USDT"].available == Decimal("10000.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["BTC"].available == Decimal("0E-8")
