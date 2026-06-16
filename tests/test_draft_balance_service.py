from decimal import Decimal

import pytest

from app.core.errors import AppError, NotFoundError
from app.models.draft_balance import DraftBalance
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.services.draft_balance import DraftBalanceService


def create_service(session) -> DraftBalanceService:
    return DraftBalanceService(DraftBalanceRepository(session), BotRepository(session))


def assets_by_symbol(snapshot):
    return {asset.asset: asset for asset in snapshot.assets}


def count_asset_rows(session, *, bot_id: int, asset: str) -> int:
    return session.query(DraftBalance).filter(DraftBalance.bot_id == bot_id, DraftBalance.asset == asset).count()


def test_reserve_moves_available_to_locked(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)

    snapshot = service.reserve_bot_draft_balance_asset(bot.id, "usdt", Decimal("62"))

    usdt = assets_by_symbol(snapshot)["USDT"]
    assert usdt.available == Decimal("9938.00000000")
    assert usdt.locked == Decimal("62.00000000")
    assert usdt.total == Decimal("10000.00000000")


def test_reserve_rejects_insufficient_available_balance(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)

    with pytest.raises(AppError) as exc_info:
        service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("10000.01"))

    assert exc_info.value.error_code == "insufficient_draft_balance_available"
    assert exc_info.value.status_code == 409
    usdt = assets_by_symbol(service.get_bot_draft_balance(bot.id))["USDT"]
    assert usdt.available == Decimal("10000.00000000")
    assert usdt.locked == Decimal("0E-8")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01")])
def test_reserve_rejects_zero_or_negative_amount(db_session, bot_stack_factory, amount) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)

    with pytest.raises(AppError) as exc_info:
        service.reserve_bot_draft_balance_asset(bot.id, "USDT", amount)

    assert exc_info.value.error_code == "invalid_draft_balance_amount"
    assert exc_info.value.status_code == 422


def test_release_moves_locked_back_to_available(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)
    service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("62"))

    snapshot = service.release_bot_draft_balance_asset(bot.id, "USDT", Decimal("62"))

    usdt = assets_by_symbol(snapshot)["USDT"]
    assert usdt.available == Decimal("10000.00000000")
    assert usdt.locked == Decimal("0E-8")


def test_release_rejects_insufficient_locked_balance(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)

    with pytest.raises(AppError) as exc_info:
        service.release_bot_draft_balance_asset(bot.id, "USDT", Decimal("1"))

    assert exc_info.value.error_code == "insufficient_draft_balance_locked"
    assert exc_info.value.status_code == 409


def test_apply_buy_fill_consumes_quote_locked_and_increases_base_available(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)
    service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("62"))

    snapshot = service.apply_draft_balance_buy_fill(
        bot.id,
        base_asset="BTC",
        quote_asset="USDT",
        received_base_amount=Decimal("0.001"),
        spent_quote_amount=Decimal("62"),
    )

    assets = assets_by_symbol(snapshot)
    assert assets["USDT"].available == Decimal("9938.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert assets["BTC"].available == Decimal("0.00100000")
    assert assets["BTC"].locked == Decimal("0E-8")


def test_apply_sell_fill_consumes_base_locked_and_increases_quote_available(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(
        bot.id,
        defaults={
            "BTC": (Decimal("0.004"), Decimal("0.001")),
            "USDT": (Decimal("10000"), Decimal("0")),
        },
    )

    snapshot = service.apply_draft_balance_sell_fill(
        bot.id,
        base_asset="BTC",
        quote_asset="USDT",
        sold_base_amount=Decimal("0.001"),
        received_quote_amount=Decimal("65"),
    )

    assets = assets_by_symbol(snapshot)
    assert assets["BTC"].available == Decimal("0.00400000")
    assert assets["BTC"].locked == Decimal("0E-8")
    assert assets["USDT"].available == Decimal("10065.00000000")
    assert assets["USDT"].locked == Decimal("0E-8")


def test_buy_fill_creates_missing_base_asset_row(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id, defaults={"USDT": (Decimal("100"), Decimal("25"))})

    snapshot = service.apply_draft_balance_buy_fill(
        bot.id,
        base_asset="eth",
        quote_asset="usdt",
        received_base_amount=Decimal("0.5"),
        spent_quote_amount=Decimal("25"),
    )

    assets = assets_by_symbol(snapshot)
    assert assets["ETH"].available == Decimal("0.50000000")
    assert assets["ETH"].locked == Decimal("0E-8")
    assert count_asset_rows(db_session, bot_id=bot.id, asset="ETH") == 1


def test_sell_fill_creates_missing_quote_asset_row(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id, defaults={"ETH": (Decimal("1"), Decimal("0.5"))})

    snapshot = service.apply_draft_balance_sell_fill(
        bot.id,
        base_asset="eth",
        quote_asset="usdt",
        sold_base_amount=Decimal("0.5"),
        received_quote_amount=Decimal("90.25"),
    )

    assets = assets_by_symbol(snapshot)
    assert assets["USDT"].available == Decimal("90.25000000")
    assert assets["USDT"].locked == Decimal("0E-8")
    assert count_asset_rows(db_session, bot_id=bot.id, asset="USDT") == 1


def test_repeated_operations_do_not_create_duplicate_asset_rows(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id)

    service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("10"))
    service.release_bot_draft_balance_asset(bot.id, "usdt", Decimal("5"))
    service.reserve_bot_draft_balance_asset(bot.id, "usdt", Decimal("5"))
    service.apply_draft_balance_buy_fill(
        bot.id,
        base_asset="btc",
        quote_asset="usdt",
        received_base_amount=Decimal("0.001"),
        spent_quote_amount=Decimal("10"),
    )

    assert count_asset_rows(db_session, bot_id=bot.id, asset="USDT") == 1
    assert count_asset_rows(db_session, bot_id=bot.id, asset="BTC") == 1


def test_decimal_values_remain_exact(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)
    service.reset_bot_draft_balance(bot.id, defaults={"USDT": (Decimal("1.23456789"), Decimal("0"))})

    snapshot = service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("0.00000001"))

    usdt = assets_by_symbol(snapshot)["USDT"]
    assert usdt.available == Decimal("1.23456788")
    assert usdt.locked == Decimal("0.00000001")
    assert usdt.total == Decimal("1.23456789")


def test_missing_bot_raises_project_style_not_found(db_session) -> None:
    service = create_service(db_session)

    with pytest.raises(NotFoundError) as exc_info:
        service.reserve_bot_draft_balance_asset(999999, "USDT", Decimal("1"))

    assert exc_info.value.error_code == "bot_not_found"
    assert exc_info.value.status_code == 404


def test_missing_asset_raises_project_style_not_found(db_session, bot_stack_factory) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    service = create_service(db_session)

    with pytest.raises(NotFoundError) as exc_info:
        service.reserve_bot_draft_balance_asset(bot.id, "USDT", Decimal("1"))

    assert exc_info.value.error_code == "draft_balance_asset_not_found"
    assert exc_info.value.status_code == 404
