from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.paper_position import PaperPositionRepository
from app.services.paper_position import PaperPositionService

PUBLIC_FIELDS = {
    "bot_id",
    "symbol",
    "base_asset",
    "quote_asset",
    "quantity",
    "average_entry_price",
    "realized_pnl",
    "market_price",
    "unrealized_pnl",
    "position_value",
    "updated_at",
}


def configure_api(configure_app_state, stub_market_data_service, noop_bot_runner) -> None:
    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=noop_bot_runner,
    )


def get_position(client: TestClient, bot_id: int):
    return client.get(f"/api/v1/bots/{bot_id}/paper-position")


def seed_buy(
    session,
    *,
    bot_id: int,
    symbol: str = "BTCUSDT",
    base_asset: str = "BTC",
    quote_asset: str = "USDT",
    quantity: str = "2",
    fill_price: str = "100",
    fee: str = "0",
) -> None:
    PaperPositionService(PaperPositionRepository(session)).apply_buy_fill(
        bot_id=bot_id,
        symbol=symbol,
        base_asset=base_asset,
        quote_asset=quote_asset,
        quantity=Decimal(quantity),
        fill_price=Decimal(fill_price),
        fee=Decimal(fee),
    )


def test_empty_position_response(
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
        response = get_position(client, bot_id)

    assert response.status_code == 200
    assert response.json() == {
        "bot_id": bot_id,
        "symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "quantity": "0",
        "average_entry_price": "0",
        "realized_pnl": "0",
        "market_price": None,
        "unrealized_pnl": None,
        "position_value": None,
        "updated_at": None,
    }


def test_buy_position_is_visible_via_api(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        seed_buy(session, bot_id=bot.id, quantity="2", fill_price="100", fee="1")
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_position(client, bot_id)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == PUBLIC_FIELDS
    assert body["quantity"] == "2"
    assert body["average_entry_price"] == "100.5"
    assert body["realized_pnl"] == "0"
    assert body["updated_at"] is not None


def test_sell_realized_pnl_is_visible_via_api(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        service = PaperPositionService(PaperPositionRepository(session))
        seed_buy(session, bot_id=bot.id, quantity="2", fill_price="100")
        service.apply_sell_fill(
            bot_id=bot.id,
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quantity=Decimal("0.5"),
            fill_price=Decimal("120"),
            fee=Decimal("1"),
        )
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_position(client, bot_id)

    body = response.json()
    assert response.status_code == 200
    assert body["quantity"] == "1.5"
    assert body["average_entry_price"] == "100"
    assert body["realized_pnl"] == "9"


def test_local_market_price_computes_unrealized_pnl_and_position_value(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        seed_buy(session, bot_id=bot.id, quantity="2", fill_price="100")
        bot_id = bot.id
    stub_market_data_service.set_price("BTCUSDT", "125")
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_position(client, bot_id)

    body = response.json()
    assert response.status_code == 200
    assert body["market_price"] == "125"
    assert body["position_value"] == "250"
    assert body["unrealized_pnl"] == "50"


def test_missing_local_price_does_not_fail(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        seed_buy(session, bot_id=bot.id)
        bot_id = bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_position(client, bot_id)

    body = response.json()
    assert response.status_code == 200
    assert body["quantity"] == "2"
    assert body["market_price"] is None
    assert body["unrealized_pnl"] is None
    assert body["position_value"] is None


def test_another_bots_position_is_not_exposed(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, selected_bot, _ = bot_stack_factory(session)
        _, other_bot, _ = bot_stack_factory(session, name="Other Bot")
        seed_buy(session, bot_id=other_bot.id, quantity="3", fill_price="50")
        selected_bot_id = selected_bot.id
        other_bot_id = other_bot.id
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        selected_response = get_position(client, selected_bot_id)
        other_response = get_position(client, other_bot_id)

    assert selected_response.status_code == 200
    assert selected_response.json()["quantity"] == "0"
    assert selected_response.json()["realized_pnl"] == "0"
    assert other_response.status_code == 200
    assert other_response.json()["quantity"] == "3"
    assert other_response.json()["average_entry_price"] == "50"


def test_missing_bot_returns_existing_bot_not_found_shape(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_api(configure_app_state, stub_market_data_service, noop_bot_runner)

    with TestClient(app) as client:
        response = get_position(client, 999999)

    assert response.status_code == 404
    assert response.json()["error_code"] == "bot_not_found"


def test_public_paper_position_api_is_read_only() -> None:
    routes = {
        route.path: route.methods
        for route in app.routes
        if getattr(route, "path", "") == "/api/v1/bots/{bot_id}/paper-position"
    }

    assert routes == {"/api/v1/bots/{bot_id}/paper-position": {"GET"}}
