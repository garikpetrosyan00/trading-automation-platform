from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.execution_profile import ExecutionProfileRepository


def test_execution_profile_stores_persisted_risk_limits(db_session, bot_stack_factory) -> None:
    _, _, profile = bot_stack_factory(db_session)
    assert profile is not None

    profile.max_trade_quantity = Decimal("0.25")
    profile.max_position_quantity = Decimal("1.5")
    profile.stop_loss_percent = Decimal("5")
    db_session.add(profile)
    db_session.commit()

    persisted = ExecutionProfileRepository(db_session).get_by_bot_id(profile.bot_id)

    assert persisted is not None
    assert persisted.max_trade_quantity == Decimal("0.25000000")
    assert persisted.max_position_quantity == Decimal("1.50000000")
    assert persisted.stop_loss_percent == Decimal("5.00000000")


def test_execution_profile_api_reads_and_updates_risk_limits(
    db_session_factory,
    stub_market_data_service,
    bot_runner_factory,
    bot_stack_factory,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        _, bot, profile = bot_stack_factory(session)
        assert profile is not None
        profile.max_trade_quantity = Decimal("0.25")
        session.add(profile)
        session.commit()
        bot_id = bot.id

    configure_app_state(
        market_data_service=stub_market_data_service,
        bot_runner=bot_runner_factory(),
    )

    with TestClient(app) as client:
        get_response = client.get(f"/api/v1/bots/{bot_id}/execution-profile")
        patch_response = client.patch(
            f"/api/v1/bots/{bot_id}/execution-profile",
            json={
                "max_position_quantity": "1.5",
                "stop_loss_percent": "5",
            },
        )

    assert get_response.status_code == 200
    assert get_response.json()["max_trade_quantity"] == "0.25000000"
    assert get_response.json()["max_position_quantity"] is None
    assert get_response.json()["stop_loss_percent"] is None

    assert patch_response.status_code == 200
    assert patch_response.json()["max_trade_quantity"] == "0.25000000"
    assert patch_response.json()["max_position_quantity"] == "1.50000000"
    assert patch_response.json()["stop_loss_percent"] == "5.00000000"
