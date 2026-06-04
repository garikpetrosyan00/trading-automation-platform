import asyncio
import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.engine.bot_runner import BotRunner, RunnerConfig
from app.main import app
from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import (
    BinanceInvalidOrderResponseError,
    BinanceOrderHttpResponse,
    BinanceTestnetOrderClientError,
)


API_KEY = "runtime-api-key"
API_SECRET = "runtime-api-secret"


class RecordingBinanceOrderClient:
    def __init__(self, response: BinanceOrderHttpResponse | None = None, exception: Exception | None = None):
        self.response = response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 98765,
                "clientOrderId": "exchange-client-id",
                "status": "FILLED",
                "executedQty": "0.1",
                "cummulativeQuoteQty": "10",
                "fills": [{"price": "100", "qty": "0.1", "commission": "0.001"}],
            },
        )
        self.exception = exception
        self.calls: list[dict] = []

    def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        return self.response


def test_paper_bot_still_uses_simulated_execution_and_never_calls_binance(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    _, bot, _ = bot_stack_factory(db_session)
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    assert client.calls == []
    orders = PortfolioRepository(db_session).list_orders()
    assert len(orders) == 1
    assert orders[0].mode == "paper"


def test_testnet_bot_runtime_submits_with_real_client_factory_and_persists_safe_attempt(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
    configure_app_state,
    noop_bot_runner,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    repository = PortfolioRepository(db_session)
    assert len(client.calls) == 1
    assert client.calls[0]["symbol"] == "BTCUSDT"
    assert client.calls[0]["side"] == "BUY"
    assert client.calls[0]["newClientOrderId"] == attempts[0].metadata_["client_order_id"]
    assert re.fullmatch(r"tap_[a-f0-9]{32}", client.calls[0]["newClientOrderId"])
    assert attempts[0].mode == "testnet"
    assert attempts[0].broker == "binance_testnet"
    assert attempts[0].final_status == "order_created"
    assert attempts[0].metadata_["exchange_order_id"] == "98765"
    assert attempts[0].metadata_["exchange_client_order_id"] == "exchange-client-id"
    assert attempts[0].metadata_["exchange_status"] == "FILLED"
    assert attempts[0].metadata_["status_code"] == 200
    assert attempts[0].metadata_["daily_order_count"] == 1
    assert_no_secret_leak(str(attempts[0].metadata_))
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before

    configure_app_state(market_data_service=stub_market_data_service, bot_runner=noop_bot_runner)
    with TestClient(app) as api_client:
        response = api_client.get(f"/api/v1/bots/{bot.id}/execution-attempts")

    assert response.status_code == 200
    assert response.json()[0]["metadata"]["client_order_id"] == client.calls[0]["newClientOrderId"]
    assert_no_secret_leak(response.text)


@pytest.mark.parametrize(
    ("config_overrides", "expected_reason"),
    [
        ({"binance_testnet_broker_enabled": False}, "testnet_broker_disabled"),
        ({"binance_testnet_order_submission_enabled": False}, "testnet_order_submission_disabled"),
        ({"execution_global_enabled": False}, "execution_global_disabled"),
        ({"binance_testnet_api_key": None}, "missing_testnet_credentials"),
        ({"binance_testnet_api_secret": None}, "missing_testnet_credentials"),
    ],
)
def test_testnet_runtime_gates_block_without_http_call(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    config_overrides,
    expected_reason,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client, **config_overrides)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert client.calls == []
    assert len(attempts) == 1
    assert attempts[0].final_reason == expected_reason
    assert attempts[0].mode == "testnet"


def test_testnet_runtime_safety_rejection_blocks_without_http_call(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    db_session.add(ExecutionDailyQuotaUsage(bot_id=bot.id, utc_day=runner_day(), accepted_order_count=1))
    db_session.commit()
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        execution_max_daily_order_count=1,
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert client.calls == []
    assert attempts[0].final_reason == "max_daily_order_count_exceeded"
    assert attempts[0].final_status == "blocked_by_safety"


def test_testnet_runtime_max_notional_rejection_blocks_without_http_call(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        execution_max_order_notional=Decimal("5"),
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert client.calls == []
    assert attempts[0].final_reason == "max_order_notional_exceeded"
    assert attempts[0].requested_price == Decimal("95.00000000")
    assert attempts[0].metadata_["notional"] == "9.50000000"


@pytest.mark.parametrize(
    ("client", "expected_reason", "expected_status"),
    [
        (
            RecordingBinanceOrderClient(
                response=BinanceOrderHttpResponse(
                    status_code=400,
                    payload={"code": -2010, "msg": "Account has insufficient balance"},
                )
            ),
            "binance_testnet_order_rejected",
            "rejected_by_broker",
        ),
        (
            RecordingBinanceOrderClient(exception=BinanceInvalidOrderResponseError("invalid json")),
            "invalid_binance_response",
            "rejected_by_broker",
        ),
        (
            RecordingBinanceOrderClient(exception=BinanceTestnetOrderClientError("timeout")),
            "binance_testnet_request_failed",
            "rejected_by_broker",
        ),
    ],
)
def test_testnet_runtime_persists_safe_binance_failures(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    client,
    expected_reason,
    expected_status,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert len(client.calls) == 1
    assert attempts[0].final_reason == expected_reason
    assert attempts[0].final_status == expected_status
    assert attempts[0].metadata_["client_order_id"] == client.calls[0]["newClientOrderId"]
    assert_no_secret_leak(str(attempts[0].metadata_))


def test_testnet_runtime_dry_run_persists_safe_attempt_without_http_call(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        binance_testnet_dry_run_enabled=True,
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert client.calls == []
    assert attempts[0].final_reason == "testnet_order_submission_dry_run"
    assert attempts[0].metadata_["client_order_id"].startswith("tap_")
    assert attempts[0].metadata_["signed"] is True
    assert_no_secret_leak(str(attempts[0].metadata_))


def test_live_bot_remains_blocked_and_never_calls_binance(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False)
    client = RecordingBinanceOrderClient()
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert client.calls == []
    assert attempts[0].mode == "live"
    assert attempts[0].final_reason == "live_mode_not_implemented"
    assert PortfolioRepository(db_session).list_orders() == []


def build_testnet_runner(db_session_factory, market_data_service, client, **config_overrides) -> BotRunner:
    config_values = {
        "enabled": True,
        "poll_interval_seconds": 3600,
        "simulation_enabled": True,
        "simulation_fee_bps": Decimal("0"),
        "simulation_slippage_bps": Decimal("0"),
        "execution_global_enabled": True,
        "binance_testnet_broker_enabled": True,
        "binance_testnet_order_submission_enabled": True,
        "binance_testnet_base_url": "https://testnet.binance.vision",
        "binance_testnet_api_key": API_KEY,
        "binance_testnet_api_secret": API_SECRET,
        "binance_testnet_timeout_seconds": 5,
        "binance_testnet_recv_window": 5000,
    }
    config_values.update(config_overrides)
    return BotRunner(
        session_factory=db_session_factory,
        market_data_service=market_data_service,
        config=RunnerConfig(**config_values),
        now_provider=runner_daytime,
        binance_order_client_factory=lambda _: client,
    )


def runner_daytime():
    from datetime import datetime, timezone

    return datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)


def runner_day():
    return runner_daytime().date()


def assert_no_secret_leak(serialized: str) -> None:
    assert API_KEY not in serialized
    assert API_SECRET not in serialized
    assert "signature" not in serialized.lower()
    assert "X-MBX-APIKEY" not in serialized
    assert "signed request" not in serialized.lower()
