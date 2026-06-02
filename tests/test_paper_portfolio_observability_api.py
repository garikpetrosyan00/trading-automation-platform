from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_accounting_event import PaperAccountingEvent
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.portfolio import PortfolioRepository
from app.services.paper_portfolio import PaperPortfolioService
from app.services.portfolio import PortfolioService
from app.services.portfolio_account import PortfolioAccountService


def apply_fill(
    session,
    *,
    symbol: str = "BTCUSDT",
    side: str,
    quantity: Decimal,
    fill_price: Decimal,
    fee: Decimal = Decimal("0"),
) -> None:
    fill = SimulatedFill(
        order_id=1,
        symbol=symbol,
        side=side,
        quantity=quantity,
        fill_quantity=quantity,
        fill_price=fill_price,
        fee=fee,
        source="paper",
    )
    PaperPortfolioService(PortfolioRepository(session)).apply_fill(fill)
    session.commit()


def get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state) -> dict:
    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    with TestClient(app) as client:
        response = client.get("/api/v1/paper-portfolio")
    assert response.status_code == 200
    return response.json()


def test_empty_paper_portfolio_response_without_account(db_session, stub_market_data_service) -> None:
    snapshot = PortfolioService(PortfolioRepository(db_session), stub_market_data_service).get_paper_snapshot()

    assert snapshot.account_currency == "USDT"
    assert snapshot.cash_balance == Decimal("0")
    assert snapshot.positions_market_value == Decimal("0")
    assert snapshot.total_equity == Decimal("0")
    assert snapshot.open_position_count == 0
    assert snapshot.positions == []
    assert snapshot.updated_at is None


def test_cash_only_paper_portfolio_response(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    assert body["account_currency"] == "USD"
    assert body["cash_balance"] == "10000.00000000"
    assert body["positions_market_value"] == "0"
    assert body["total_equity"] == "10000.00000000"
    assert body["total_realized_pnl"] == "0"
    assert body["total_unrealized_pnl"] == "0"
    assert body["open_position_count"] == 0
    assert body["positions"] == []
    assert body["updated_at"] is not None


def test_buy_created_open_position_reflected_in_response(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, side="buy", quantity=Decimal("2"), fill_price=Decimal("100"))

    stub_market_data_service.set_price("BTCUSDT", "125")
    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    position = body["positions"][0]
    assert body["open_position_count"] == 1
    assert position["symbol"] == "BTCUSDT"
    assert position["quantity"] == "2.00000000"
    assert position["average_entry_price"] == "100.00000000"
    assert position["latest_market_price"] == "125"
    assert position["market_value"] == "250.00000000"
    assert position["unrealized_pnl"] == "50.00000000"
    assert position["unrealized_pnl_percent"] == "25.00"
    assert position["price_available"] is True


def test_multiple_positions_are_ordered_by_symbol(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, symbol="ETHUSDT", side="buy", quantity=Decimal("1"), fill_price=Decimal("10"))
        apply_fill(session, symbol="BTCUSDT", side="buy", quantity=Decimal("1"), fill_price=Decimal("20"))

    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    assert [position["symbol"] for position in body["positions"]] == ["BTCUSDT", "ETHUSDT"]


def test_weighted_average_entry_after_multiple_buys(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, side="buy", quantity=Decimal("1"), fill_price=Decimal("100"))
        apply_fill(session, side="buy", quantity=Decimal("3"), fill_price=Decimal("140"))

    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    assert body["positions"][0]["average_entry_price"] == "130.00000000"


def test_partial_sell_reflected_correctly(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, side="buy", quantity=Decimal("2"), fill_price=Decimal("100"))
        apply_fill(session, side="sell", quantity=Decimal("0.5"), fill_price=Decimal("130"))

    stub_market_data_service.set_price("BTCUSDT", "120")
    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    position = body["positions"][0]
    assert position["quantity"] == "1.50000000"
    assert position["average_entry_price"] == "100.00000000"
    assert position["realized_pnl"] == "15.00000000"
    assert position["market_value"] == "180.00000000"
    assert position["unrealized_pnl"] == "30.00000000"
    assert body["total_realized_pnl"] == "15.00000000"


def test_full_sell_removes_open_position_and_keeps_realized_total(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, side="buy", quantity=Decimal("1"), fill_price=Decimal("100"))
        apply_fill(session, side="sell", quantity=Decimal("1"), fill_price=Decimal("125"))

    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    assert body["open_position_count"] == 0
    assert body["positions"] == []
    assert body["total_realized_pnl"] == "25.00000000"


def test_missing_latest_price_returns_null_position_valuation(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, side="buy", quantity=Decimal("2"), fill_price=Decimal("100"))

    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    position = body["positions"][0]
    assert position["latest_market_price"] is None
    assert position["latest_price"] is None
    assert position["market_value"] is None
    assert position["unrealized_pnl"] is None
    assert position["unrealized_pnl_percent"] is None
    assert position["price_available"] is False
    assert body["cash_balance"] == "800.00000000"
    assert body["positions_market_value"] == "0"
    assert body["total_equity"] == "800.00000000"


def test_multiple_positions_aggregate_totals(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        apply_fill(session, symbol="BTCUSDT", side="buy", quantity=Decimal("2"), fill_price=Decimal("100"))
        apply_fill(session, symbol="ETHUSDT", side="buy", quantity=Decimal("3"), fill_price=Decimal("50"))
        apply_fill(session, symbol="BTCUSDT", side="sell", quantity=Decimal("1"), fill_price=Decimal("110"))

    stub_market_data_service.set_price("BTCUSDT", "130")
    stub_market_data_service.set_price("ETHUSDT", "40")
    body = get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    assert body["positions_market_value"] == "250.00000000"
    assert body["total_market_value"] == "250.00000000"
    assert body["total_equity"] == "1010.00000000"
    assert body["total_realized_pnl"] == "10.00000000"
    assert body["total_unrealized_pnl"] == "0"


def test_paper_portfolio_endpoint_is_read_only(
    db_session_factory,
    stub_market_data_service,
    noop_bot_runner,
    configure_app_state,
) -> None:
    with db_session_factory() as session:
        PortfolioAccountService(PortfolioRepository(session)).ensure_account("USD", Decimal("1000"))
        before = {
            "orders": session.query(SimulatedOrder).count(),
            "fills": session.query(SimulatedFill).count(),
            "attempts": session.query(ExecutionAttempt).count(),
            "events": session.query(PaperAccountingEvent).count(),
            "quota": session.query(ExecutionDailyQuotaUsage).count(),
        }

    get_snapshot(db_session_factory, stub_market_data_service, noop_bot_runner, configure_app_state)

    with db_session_factory() as session:
        after = {
            "orders": session.query(SimulatedOrder).count(),
            "fills": session.query(SimulatedFill).count(),
            "attempts": session.query(ExecutionAttempt).count(),
            "events": session.query(PaperAccountingEvent).count(),
            "quota": session.query(ExecutionDailyQuotaUsage).count(),
        }

    assert after == before
