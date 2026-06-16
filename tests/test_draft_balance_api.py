from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.draft_balance import DraftBalance
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.draft_balance import DraftBalanceService


def assets_by_symbol(payload: dict) -> dict[str, dict]:
    return {asset["asset"]: asset for asset in payload["assets"]}


def test_get_draft_balance_before_reset_returns_empty_assets(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"bot_id", "assets"}
    assert body == {"bot_id": bot_id, "assets": []}


def test_reset_draft_balance_creates_default_assets(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")

    assert response.status_code == 200
    assert response.json() == {
        "bot_id": bot_id,
        "assets": [
            {"asset": "BTC", "available": "0", "locked": "0", "total": "0"},
            {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"},
        ],
    }


def test_repeated_reset_is_idempotent_and_does_not_duplicate_rows(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        first = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")
        second = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    with db_session_factory() as session:
        rows = session.query(DraftBalance).filter(DraftBalance.bot_id == bot_id).all()
    assert len(rows) == 2


def test_decimal_values_are_returned_as_strings(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        service = DraftBalanceService(DraftBalanceRepository(session), BotRepository(session))
        service.reset_bot_draft_balance(
            bot.id,
            defaults={"eth": (Decimal("1.25000000"), Decimal("0.75000000"))},
        )
        bot_id = bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")

    assert response.status_code == 200
    assert response.json()["assets"] == [
        {"asset": "ETH", "available": "1.25", "locked": "0.75", "total": "2"}
    ]
    assert all(isinstance(value, str) for value in response.json()["assets"][0].values())


def test_reset_reinitializes_only_selected_bot_draft_balance(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, _ = bot_stack_factory(session)
        _, other_bot, _ = bot_stack_factory(session, name="Other Bot")
        service = DraftBalanceService(DraftBalanceRepository(session), BotRepository(session))
        service.reset_bot_draft_balance(
            bot.id,
            defaults={
                "USDT": (Decimal("42"), Decimal("3")),
                "ETH": (Decimal("1.5"), Decimal("0.25")),
            },
        )
        service.reset_bot_draft_balance(
            other_bot.id,
            defaults={
                "USDT": (Decimal("200"), Decimal("10")),
                "ETH": (Decimal("2"), Decimal("0")),
            },
        )
        bot_id = bot.id
        other_bot_id = other_bot.id

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")
        other_response = client.get(f"/api/v1/bots/{other_bot_id}/draft-balance")

    assert response.status_code == 200
    assert response.json() == {
        "bot_id": bot_id,
        "assets": [
            {"asset": "BTC", "available": "0", "locked": "0", "total": "0"},
            {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"},
        ],
    }
    assert other_response.status_code == 200
    assert other_response.json() == {
        "bot_id": other_bot_id,
        "assets": [
            {"asset": "ETH", "available": "2", "locked": "0", "total": "2"},
            {"asset": "USDT", "available": "200", "locked": "10", "total": "210"},
        ],
    }


def test_public_draft_balance_api_remains_read_and_reset_only() -> None:
    draft_routes = {
        route.path: route.methods
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/bots/{bot_id}/draft-balance")
    }

    assert draft_routes == {
        "/api/v1/bots/{bot_id}/draft-balance": {"GET"},
        "/api/v1/bots/{bot_id}/draft-balance/reset": {"POST"},
    }


def test_manual_paper_buy_updates_draft_balance_and_preserves_audit_visibility(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
    set_latest_market_price,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        strategy, bot, _ = bot_stack_factory(session, name="Draft API Bot", description="Draft API integration")
        _, other_bot, _ = bot_stack_factory(session, name="Other Draft API Bot")
        bot_id = bot.id
        strategy_id = strategy.id
        other_bot_id = other_bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        reset_response = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")
        other_reset_response = client.post(f"/api/v1/bots/{other_bot_id}/draft-balance/reset")
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        set_latest_market_price("95")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        draft_response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")
        other_draft_response = client.get(f"/api/v1/bots/{other_bot_id}/draft-balance")
        orders_response = client.get(f"/api/v1/bots/{bot_id}/orders")
        attempts_response = client.get(f"/api/v1/bots/{bot_id}/execution-attempts")

    assert reset_response.status_code == 200
    assert other_reset_response.status_code == 200
    assert start_response.status_code == 200

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "bought"
    assert run_response.json()["message"] == "buy_filled"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "buy_filled"

    assert draft_response.status_code == 200
    assets = assets_by_symbol(draft_response.json())
    assert assets["USDT"] == {"asset": "USDT", "available": "9990.5", "locked": "0", "total": "9990.5"}
    assert assets["BTC"] == {"asset": "BTC", "available": "0.1", "locked": "0", "total": "0.1"}

    assert other_draft_response.status_code == 200
    assert other_draft_response.json() == {
        "bot_id": other_bot_id,
        "assets": [
            {"asset": "BTC", "available": "0", "locked": "0", "total": "0"},
            {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"},
        ],
    }

    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert len(orders) == 1
    assert orders[0]["bot_id"] == bot_id
    assert orders[0]["strategy_id"] == strategy_id
    assert orders[0]["side"] == "buy"
    assert orders[0]["status"] == "filled"
    assert orders[0]["fill_count"] == 1

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert len(attempts) == 1
    assert attempts[0]["final_status"] == "filled"
    assert attempts[0]["order_id"] == orders[0]["id"]
    assert attempts[0]["broker"] == "paper"
    assert attempts[0]["mode"] == "paper"


def test_manual_paper_buy_with_insufficient_draft_balance_rejects_without_paper_mutation(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
    set_latest_market_price,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="Insufficient Draft API Bot")
        DraftBalanceService(DraftBalanceRepository(session), BotRepository(session)).reset_bot_draft_balance(
            bot.id,
            defaults={"USDT": (Decimal("1"), Decimal("0"))},
        )
        bot_id = bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        start_response = client.post(f"/api/v1/bots/{bot_id}/start")
        set_latest_market_price("95")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        draft_response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")
        orders_response = client.get(f"/api/v1/bots/{bot_id}/orders")
        attempts_response = client.get(f"/api/v1/bots/{bot_id}/execution-attempts")

    assert start_response.status_code == 200
    assert run_response.status_code == 200
    assert run_response.json()["action"] == "skipped"
    assert run_response.json()["message"] == "order_rejected"
    assert run_response.json()["recent_activity_preview"][0]["message"] == "order_rejected"

    assert draft_response.status_code == 200
    assert draft_response.json() == {
        "bot_id": bot_id,
        "assets": [{"asset": "USDT", "available": "1", "locked": "0", "total": "1"}],
    }

    assert orders_response.status_code == 200
    assert orders_response.json() == []

    assert attempts_response.status_code == 200
    attempts = attempts_response.json()
    assert len(attempts) == 1
    assert attempts[0]["final_status"] == "rejected_by_broker"
    assert attempts[0]["final_reason"] == "insufficient_draft_balance_available"
    assert attempts[0]["order_id"] is None

    with db_session_factory() as session:
        repository = PortfolioRepository(session)
        assert repository.list_orders() == []
        assert repository.list_fills() == []
        assert repository.get_position_by_symbol("BTCUSDT") is None


def test_reset_after_manual_paper_execution_reinitializes_only_selected_bot_draft_balance(
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    bot_runner_factory,
    configure_app_state,
    funded_account,
    set_latest_market_price,
) -> None:
    with db_session_factory() as session:
        funded_account(session)
        _, bot, _ = bot_stack_factory(session, name="Reset After Execution Bot")
        _, other_bot, _ = bot_stack_factory(session, name="Reset Other Bot")
        bot_id = bot.id
        other_bot_id = other_bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")
        client.post(f"/api/v1/bots/{other_bot_id}/draft-balance/reset")
        client.post(f"/api/v1/bots/{bot_id}/start")
        set_latest_market_price("95")
        run_response = client.post(f"/api/v1/bots/{bot_id}/run")
        changed_response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")
        reset_response = client.post(f"/api/v1/bots/{bot_id}/draft-balance/reset")
        selected_after_reset_response = client.get(f"/api/v1/bots/{bot_id}/draft-balance")
        other_after_reset_response = client.get(f"/api/v1/bots/{other_bot_id}/draft-balance")

    assert run_response.status_code == 200
    assert run_response.json()["action"] == "bought"
    assert assets_by_symbol(changed_response.json())["BTC"]["available"] == "0.1"

    expected_default = [
        {"asset": "BTC", "available": "0", "locked": "0", "total": "0"},
        {"asset": "USDT", "available": "10000", "locked": "0", "total": "10000"},
    ]
    assert reset_response.status_code == 200
    assert reset_response.json() == {"bot_id": bot_id, "assets": expected_default}
    assert selected_after_reset_response.status_code == 200
    assert selected_after_reset_response.json() == {"bot_id": bot_id, "assets": expected_default}
    assert other_after_reset_response.status_code == 200
    assert other_after_reset_response.json() == {"bot_id": other_bot_id, "assets": expected_default}


def test_missing_bot_returns_404(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)

    with TestClient(app) as client:
        get_response = client.get("/api/v1/bots/999999/draft-balance")
        reset_response = client.post("/api/v1/bots/999999/draft-balance/reset")

    assert get_response.status_code == 404
    assert get_response.json()["error_code"] == "bot_not_found"
    assert reset_response.status_code == 404
    assert reset_response.json()["error_code"] == "bot_not_found"


def test_same_asset_can_exist_for_different_bots(
    db_session,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session)
    _, other_bot, _ = bot_stack_factory(db_session, name="Other Bot")
    service = DraftBalanceService(DraftBalanceRepository(db_session), BotRepository(db_session))

    service.reset_bot_draft_balance(bot.id, defaults={"usdt": (Decimal("100"), Decimal("0"))})
    service.reset_bot_draft_balance(other_bot.id, defaults={"USDT": (Decimal("200"), Decimal("0"))})

    rows = db_session.query(DraftBalance).filter(DraftBalance.asset == "USDT").order_by(DraftBalance.bot_id.asc()).all()
    assert [(row.bot_id, row.available) for row in rows] == [
        (bot.id, Decimal("100.00000000")),
        (other_bot.id, Decimal("200.00000000")),
    ]
