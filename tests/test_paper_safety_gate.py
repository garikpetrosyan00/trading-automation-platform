from decimal import Decimal

import pytest

from app.core.errors import AppError, NotFoundError
from app.models.draft_balance import DraftBalance
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_equity_snapshot import PaperEquitySnapshot
from app.models.paper_position import PaperPosition
from app.models.run_event import RunEvent
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_position import PaperPositionRepository
from app.services.draft_balance import DraftBalanceService
from app.services.paper_position import PaperPositionService
from app.services.paper_safety_gate import PaperSafetyGateService


def build_gate(session, *, paper_trading_enabled: bool = True) -> PaperSafetyGateService:
    return PaperSafetyGateService(
        bot_repository=BotRepository(session),
        draft_balance_repository=DraftBalanceRepository(session),
        paper_position_repository=PaperPositionRepository(session),
        paper_trading_enabled=paper_trading_enabled,
    )


def reset_balance(session, bot_id: int, defaults: dict[str, tuple[Decimal, Decimal]]) -> None:
    DraftBalanceService(DraftBalanceRepository(session), BotRepository(session)).reset_bot_draft_balance(
        bot_id,
        defaults=defaults,
    )


def seed_position(session, bot_id: int, quantity: Decimal = Decimal("1")) -> None:
    PaperPositionService(PaperPositionRepository(session)).apply_buy_fill(
        bot_id=bot_id,
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        quantity=quantity,
        fill_price=Decimal("100"),
    )


def counts(session) -> dict[str, int]:
    return {
        "orders": session.query(SimulatedOrder).count(),
        "fills": session.query(SimulatedFill).count(),
        "attempts": session.query(ExecutionAttempt).count(),
        "run_events": session.query(RunEvent).count(),
        "draft_balances": session.query(DraftBalance).count(),
        "paper_positions": session.query(PaperPosition).count(),
        "paper_equity_snapshots": session.query(PaperEquitySnapshot).count(),
    }


def test_valid_paper_buy_passes(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(db_session, bot.id, {"USDT": (Decimal("100"), Decimal("0"))})

    build_gate(db_session).validate_paper_buy_allowed(
        bot_id=bot.id,
        quote_asset="usdt",
        required_quote_amount=Decimal("99.5"),
    )


def test_valid_paper_sell_passes(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(
        db_session,
        bot.id,
        {
            "BTC": (Decimal("1"), Decimal("0")),
            "USDT": (Decimal("100"), Decimal("0")),
        },
    )
    seed_position(db_session, bot.id, Decimal("1"))

    build_gate(db_session).validate_paper_sell_allowed(
        bot_id=bot.id,
        symbol="btcusdt",
        base_asset="btc",
        quote_asset="usdt",
        quantity=Decimal("0.75"),
    )


def test_disabled_paper_trading_rejects_buy_before_balance_checks(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session, paper_trading_enabled=False).validate_paper_buy_allowed(
            bot_id=bot.id,
            quote_asset="USDT",
            required_quote_amount=Decimal("1"),
        )

    assert exc_info.value.error_code == "paper_trading_disabled"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Paper trading is disabled"


def test_disabled_paper_trading_rejects_sell_before_position_checks(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session, paper_trading_enabled=False).validate_paper_sell_allowed(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.1"),
        )

    assert exc_info.value.error_code == "paper_trading_disabled"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Paper trading is disabled"


def test_buy_rejects_insufficient_quote_balance(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(db_session, bot.id, {"USDT": (Decimal("50"), Decimal("0"))})

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session).validate_paper_buy_allowed(
            bot_id=bot.id,
            quote_asset="USDT",
            required_quote_amount=Decimal("50.01"),
        )

    assert exc_info.value.error_code == "insufficient_draft_balance_available"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Insufficient draft balance available amount"


def test_buy_rejects_missing_bot_scoped_draft_balance_context(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")

    with pytest.raises(NotFoundError) as exc_info:
        build_gate(db_session).validate_paper_buy_allowed(
            bot_id=bot.id,
            quote_asset="USDT",
            required_quote_amount=Decimal("1"),
        )

    assert exc_info.value.error_code == "draft_balance_asset_not_found"
    assert exc_info.value.status_code == 404


def test_sell_rejects_missing_paper_position(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(db_session, bot.id, {"BTC": (Decimal("1"), Decimal("0"))})

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session).validate_paper_sell_allowed(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.1"),
        )

    assert exc_info.value.error_code == "insufficient_paper_position_quantity"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Insufficient paper position quantity"


def test_sell_rejects_insufficient_paper_position_quantity(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(db_session, bot.id, {"BTC": (Decimal("1"), Decimal("0"))})
    seed_position(db_session, bot.id, Decimal("0.2"))

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session).validate_paper_sell_allowed(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.20000001"),
        )

    assert exc_info.value.error_code == "insufficient_paper_position_quantity"
    assert exc_info.value.status_code == 409


@pytest.mark.parametrize(
    ("is_paper", "execution_mode"),
    [
        (False, "live"),
        (False, "testnet"),
        (True, "testnet"),
    ],
)
def test_rejects_non_paper_live_or_testnet_configuration(
    db_session,
    bot_stack_factory,
    is_paper: bool,
    execution_mode: str,
) -> None:
    _, bot, _ = bot_stack_factory(
        db_session,
        status="active",
        is_paper=is_paper,
        execution_mode=execution_mode,
    )

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session, paper_trading_enabled=False).validate_bot_paper_execution_allowed(bot_id=bot.id)

    assert exc_info.value.error_code == "paper_execution_mode_required"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Paper execution requires a paper-mode bot"


def test_rejects_bot_that_is_not_runnable_when_required(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="paused")

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session, paper_trading_enabled=False).validate_bot_paper_execution_allowed(bot_id=bot.id)

    assert exc_info.value.error_code == "bot_not_runnable"
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "Bot is not active and runnable"


def test_rejection_does_not_create_or_mutate_execution_side_effects(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_balance(
        db_session,
        bot.id,
        {
            "BTC": (Decimal("1"), Decimal("0")),
            "USDT": (Decimal("50"), Decimal("0")),
        },
    )
    seed_position(db_session, bot.id, Decimal("1"))
    before_counts = counts(db_session)
    before_usdt = DraftBalanceRepository(db_session).get_for_bot_asset(bot_id=bot.id, asset="USDT")
    before_position = PaperPositionRepository(db_session).get_for_bot_symbol(bot_id=bot.id, symbol="BTCUSDT")
    assert before_usdt is not None
    assert before_position is not None

    with pytest.raises(AppError) as exc_info:
        build_gate(db_session).validate_paper_buy_allowed(
            bot_id=bot.id,
            quote_asset="USDT",
            required_quote_amount=Decimal("50.01"),
        )

    after_usdt = DraftBalanceRepository(db_session).get_for_bot_asset(bot_id=bot.id, asset="USDT")
    after_position = PaperPositionRepository(db_session).get_for_bot_symbol(bot_id=bot.id, symbol="BTCUSDT")
    assert exc_info.value.error_code == "insufficient_draft_balance_available"
    assert counts(db_session) == before_counts
    assert after_usdt is not None
    assert after_usdt.available == before_usdt.available == Decimal("50.00000000")
    assert after_usdt.locked == before_usdt.locked == Decimal("0E-8")
    assert after_position is not None
    assert after_position.quantity == before_position.quantity == Decimal("1.00000000")
    assert after_position.average_entry_price == before_position.average_entry_price == Decimal("100.00000000")
