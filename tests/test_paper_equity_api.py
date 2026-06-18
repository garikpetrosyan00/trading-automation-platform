from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
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

PUBLIC_FIELDS = {
    "id",
    "bot_id",
    "symbol",
    "quote_asset",
    "cash_available",
    "cash_locked",
    "base_quantity",
    "base_locked",
    "average_entry_price",
    "realized_pnl",
    "market_price",
    "position_value",
    "total_equity",
    "event_type",
    "created_at",
}


def configure_api(configure_app_state, stub_market_data_service, noop_bot_runner) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )


def get_paper_equity(client: TestClient, bot_id: int, **params):
    return client.get(f"/api/v1/bots/{bot_id}/paper-equity", params=params)


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


def create_manual_snapshot(
    session,
    *,
    bot_id: int,
    symbol: str = "BTCUSDT",
    base_asset: str = "BTC",
    quote_asset: str = "USDT",
    quantity: str = "0",
    average_entry_price: str = "0",
    realized_pnl: str = "0",
) -> None:
    if Decimal(quantity) > 0:
        PaperPositionService(PaperPositionRepository(session)).apply_buy_fill(
            bot_id=bot_id,
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            quantity=Decimal(quantity),
            fill_price=Decimal(average_entry_price) if Decimal(average_entry_price) > 0 else Decimal("1"),
            fee=Decimal("0"),
        )
        if Decimal(realized_pnl) != 0:
            position = PaperPositionRepository(session).get_for_bot_symbol(bot_id=bot_id, symbol=symbol)
            position.realized_pnl = Decimal(realized_pnl)
    service = PaperEquitySnapshotService(
        PaperEquitySnapshotRepository(session),
        DraftBalanceRepository(session),
        PaperPositionRepository(session),
    )
    service.create_snapshot(
        bot_id=bot_id,
        symbol=symbol,
        base_asset=base_asset,
        quote_asset=quote_asset,
        event_type="manual_snapshot",
    )


def test_empty_paper_equity_response_for_bot_with_no_snapshots(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_paper_equity(client, bot_id)

    assert response.status_code == 200
    assert response.json() == {
        "bot_id": bot_id,
        "count": 0,
        "items": [],
    }


def test_buy_and_sell_snapshots_are_returned_via_api(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        reset_draft_balance(session, bot_id=bot.id)
        service = build_execution_service(session, stub_market_data_service, fee_bps="10")
        stub_market_data_service.set_price("BTCUSDT", "100")
        buy_result = service.submit_order_intent(
            PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("2"))
        )
        stub_market_data_service.set_price("BTCUSDT", "120")
        sell_result = service.submit_order_intent(
            PaperOrderIntent(bot_id=bot.id, symbol="BTCUSDT", side="sell", quantity=Decimal("1"))
        )
        assert buy_result.accepted is True
        assert sell_result.accepted is True
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_paper_equity(client, bot_id)

    body = response.json()
    assert response.status_code == 200
    assert body["bot_id"] == bot_id
    assert body["count"] == 2
    assert len(body["items"]) == 2
    latest_item = body["items"][0]
    older_item = body["items"][1]
    assert set(latest_item) == PUBLIC_FIELDS
    assert "source_order_id" not in latest_item
    assert "source_fill_id" not in latest_item
    assert latest_item["event_type"] == "sell_fill"
    assert latest_item["realized_pnl"] == "19.78"
    assert latest_item["market_price"] == "120"
    assert latest_item["position_value"] == "120"
    assert latest_item["total_equity"] == "10039.68"
    assert older_item["event_type"] == "buy_fill"
    assert older_item["realized_pnl"] == "0"
    assert older_item["market_price"] == "100"


def test_paper_equity_is_isolated_by_bot(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, selected_bot, _ = bot_stack_factory(session)
        _, other_bot, _ = bot_stack_factory(session, name="Other Bot")
        reset_draft_balance(session, bot_id=other_bot.id)
        stub_market_data_service.set_price("BTCUSDT", "100")
        service = build_execution_service(session, stub_market_data_service, fee_bps="0")
        result = service.submit_order_intent(
            PaperOrderIntent(bot_id=other_bot.id, symbol="BTCUSDT", side="buy", quantity=Decimal("1"))
        )
        assert result.accepted is True
        selected_bot_id = selected_bot.id
        other_bot_id = other_bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        selected_response = get_paper_equity(client, selected_bot_id)
        other_response = get_paper_equity(client, other_bot_id)

    assert selected_response.status_code == 200
    assert selected_response.json() == {
        "bot_id": selected_bot_id,
        "count": 0,
        "items": [],
    }
    assert other_response.status_code == 200
    assert other_response.json()["count"] == 1
    assert other_response.json()["items"][0]["bot_id"] == other_bot_id


def test_paper_equity_limit_behavior(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        reset_draft_balance(
            session,
            bot_id=bot.id,
            defaults={"BTC": (Decimal("3"), Decimal("0")), "USDT": (Decimal("500"), Decimal("0"))},
        )
        create_manual_snapshot(session, bot_id=bot.id)
        create_manual_snapshot(session, bot_id=bot.id)
        create_manual_snapshot(session, bot_id=bot.id)
        session.commit()
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_paper_equity(client, bot_id, limit=2)

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 2
    assert len(body["items"]) == 2


def test_paper_equity_returns_newest_first(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        reset_draft_balance(
            session,
            bot_id=bot.id,
            defaults={"BTC": (Decimal("1"), Decimal("0")), "USDT": (Decimal("500"), Decimal("0"))},
        )
        service = PaperEquitySnapshotService(
            PaperEquitySnapshotRepository(session),
            DraftBalanceRepository(session),
            PaperPositionRepository(session),
        )
        first = service.create_snapshot(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            event_type="manual_snapshot",
        )
        second = service.create_snapshot(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            event_type="manual_snapshot",
        )
        session.commit()
        bot_id = bot.id
        first_id = first.id
        second_id = second.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_paper_equity(client, bot_id)

    items = response.json()["items"]
    assert response.status_code == 200
    assert [item["id"] for item in items[:2]] == [second_id, first_id]


def test_missing_bot_returns_existing_bot_not_found_shape(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_paper_equity(client, 999999)

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_public_paper_equity_api_is_read_only() -> None:
    routes = {
        route.path: route.methods
        for route in app.routes
        if getattr(route, "path", "") == "/api/v1/bots/{bot_id}/paper-equity"
    }

    assert routes == {"/api/v1/bots/{bot_id}/paper-equity": {"GET"}}
