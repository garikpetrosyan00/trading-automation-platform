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
    BinanceAccountHttpResponse,
    BinanceInvalidOrderResponseError,
    BinanceOrderHttpResponse,
    BinanceTestnetOrderClientError,
)
from app.services.brokers.binance_exchange_info import (
    BinanceExchangeInfo,
    BinanceExchangeInfoError,
    BinanceQuantityFilter,
    BinanceSymbolRules,
)


API_KEY = "runtime-api-key"
API_SECRET = "runtime-api-secret"


class RecordingBinanceOrderClient:
    def __init__(
        self,
        response: BinanceOrderHttpResponse | None = None,
        exception: Exception | None = None,
        query_response: BinanceOrderHttpResponse | None = None,
    ):
        self.response = response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 98765,
                "clientOrderId": "filled-by-submit-call",
                "status": "FILLED",
                "executedQty": "0.1",
                "cummulativeQuoteQty": "10",
                "fills": [{"price": "100", "qty": "0.1", "commission": "0.001"}],
            },
        )
        self.exception = exception
        self.query_response = query_response or BinanceOrderHttpResponse(
            status_code=200,
            payload={
                "symbol": "BTCUSDT",
                "orderId": 98765,
                "clientOrderId": "filled-by-submit-call",
                "status": "NEW",
                "executedQty": "0",
                "cummulativeQuoteQty": "0",
            },
        )
        self.calls: list[dict] = []
        self.query_calls: list[dict] = []

    def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        payload = dict(self.response.payload or {})
        if payload.get("clientOrderId") == "filled-by-submit-call":
            payload["clientOrderId"] = params["newClientOrderId"]
        return BinanceOrderHttpResponse(status_code=self.response.status_code, payload=payload)

    def query_signed_order(self, params: dict) -> BinanceOrderHttpResponse:
        self.query_calls.append(params)
        payload = dict(self.query_response.payload or {})
        if payload.get("clientOrderId") == "filled-by-submit-call" and self.calls:
            payload["clientOrderId"] = self.calls[0]["newClientOrderId"]
        return BinanceOrderHttpResponse(status_code=self.query_response.status_code, payload=payload)


class RecordingBinanceAccountClient:
    def __init__(self, response: BinanceAccountHttpResponse | None = None, exception: Exception | None = None):
        self.response = response or BinanceAccountHttpResponse(
            status_code=200,
            payload={
                "canTrade": True,
                "balances": [
                    {"asset": "BTC", "free": "10", "locked": "0"},
                    {"asset": "USDT", "free": "100000", "locked": "0"},
                ],
            },
        )
        self.exception = exception
        self.calls: list[dict] = []

    def fetch_signed_account(self, params: dict) -> BinanceAccountHttpResponse:
        self.calls.append(params)
        if self.exception is not None:
            raise self.exception
        return self.response


class StaticExchangeInfoProvider:
    def __init__(self, info: BinanceExchangeInfo | None = None, exception: Exception | None = None):
        self.info = info or valid_exchange_info()
        self.exception = exception
        self.calls = 0

    def get_exchange_info(self) -> BinanceExchangeInfo:
        self.calls += 1
        if self.exception is not None:
            raise self.exception
        return self.info


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
    assert attempts[0].metadata_["exchange_client_order_id"] == client.calls[0]["newClientOrderId"]
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
    public_metadata = response.json()[0]["metadata"]
    assert "client_order_id" not in public_metadata
    assert "exchange_order_id" not in public_metadata
    assert "exchange_client_order_id" not in public_metadata
    assert public_metadata["exchange_status"] == "FILLED"
    assert public_metadata["status_code"] == 200
    assert public_metadata["daily_order_count"] == 1
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
            "testnet_order_recovered_after_unknown_submission",
            "order_created",
        ),
        (
            RecordingBinanceOrderClient(exception=BinanceTestnetOrderClientError("timeout")),
            "testnet_order_recovered_after_unknown_submission",
            "order_created",
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
    if expected_status == "order_created":
        assert len(client.query_calls) == 1
        assert attempts[0].metadata_["reconciliation_resolution"] == "found"
    else:
        assert client.query_calls == []
    assert_no_secret_leak(str(attempts[0].metadata_))


def test_testnet_runtime_recovered_status_unknown_does_not_mutate_paper_portfolio(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient(exception=BinanceTestnetOrderClientError("timeout", trigger="timeout"))
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    repository = PortfolioRepository(db_session)
    assert len(client.calls) == 1
    assert len(client.query_calls) == 1
    assert attempts[0].final_status == "order_created"
    assert attempts[0].final_reason == "testnet_order_recovered_after_unknown_submission"
    assert attempts[0].metadata_["reconciliation_resolution"] == "found"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before
    assert_no_secret_leak(str(attempts[0].metadata_))


def test_testnet_runtime_unresolved_status_unknown_does_not_mutate_paper_portfolio(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient(
        exception=BinanceTestnetOrderClientError("timeout", trigger="timeout"),
        query_response=BinanceOrderHttpResponse(status_code=404, payload={"code": -2013, "msg": "NO_SUCH_ORDER"}),
    )
    runner = build_testnet_runner(db_session_factory, stub_market_data_service, client)
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    repository = PortfolioRepository(db_session)
    assert len(client.calls) == 1
    assert len(client.query_calls) == 1
    assert attempts[0].final_status == "rejected_by_broker"
    assert attempts[0].final_reason == "testnet_order_reconciliation_unresolved"
    assert attempts[0].metadata_["reconciliation_resolution"] == "unresolved"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before
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


def test_testnet_runtime_unavailable_exchange_info_blocks_before_order_submission(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    exchange_info_provider = StaticExchangeInfoProvider(
        exception=BinanceExchangeInfoError("raw response body must stay private")
    )
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        exchange_info_provider=exchange_info_provider,
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert exchange_info_provider.calls == 1
    assert client.calls == []
    assert attempts[0].final_reason == "testnet_exchange_info_unavailable"
    assert_no_secret_leak(str(attempts[0].metadata_))
    assert "raw response body" not in str(attempts[0].metadata_)


def test_testnet_runtime_invalid_filter_blocks_before_signing_and_order_submission(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    exchange_info_provider = StaticExchangeInfoProvider(
        valid_exchange_info(
            lot_size=BinanceQuantityFilter(
                filter_type="LOT_SIZE",
                min_qty=Decimal("1"),
                max_qty=Decimal("10"),
                step_size=Decimal("1"),
            )
        )
    )
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        exchange_info_provider=exchange_info_provider,
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    assert exchange_info_provider.calls == 1
    assert client.calls == []
    assert attempts[0].final_reason == "testnet_quantity_below_minimum"
    assert attempts[0].metadata_["filter_type"] == "LOT_SIZE"
    assert_no_secret_leak(str(attempts[0].metadata_))


def test_testnet_runtime_account_preflight_rejection_does_not_mutate_paper_portfolio(
    db_session,
    db_session_factory,
    stub_market_data_service,
    bot_stack_factory,
    funded_account,
) -> None:
    funded_account(db_session)
    account_before = PortfolioRepository(db_session).get_account().cash_balance
    _, bot, _ = bot_stack_factory(db_session, is_paper=False, execution_mode="testnet")
    client = RecordingBinanceOrderClient()
    account_client = RecordingBinanceAccountClient(
        BinanceAccountHttpResponse(
            status_code=200,
            payload={"canTrade": True, "balances": [{"asset": "USDT", "free": "0", "locked": "100000"}]},
        )
    )
    runner = build_testnet_runner(
        db_session_factory,
        stub_market_data_service,
        client,
        account_client=account_client,
    )
    runner.start_bot(bot.id)
    stub_market_data_service.set_price("BTCUSDT", "95")

    asyncio.run(runner.run_cycle())

    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id)
    repository = PortfolioRepository(db_session)
    assert len(account_client.calls) == 1
    assert client.calls == []
    assert attempts[0].final_reason == "testnet_insufficient_balance"
    assert attempts[0].metadata_["account_preflight_checked"] is True
    assert attempts[0].metadata_["balance_asset"] == "USDT"
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert repository.get_account().cash_balance == account_before
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


def build_testnet_runner(
    db_session_factory,
    market_data_service,
    client,
    *,
    account_client: RecordingBinanceAccountClient | None = None,
    exchange_info_provider: StaticExchangeInfoProvider | None = None,
    **config_overrides,
) -> BotRunner:
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
        binance_account_client_factory=lambda _: account_client or RecordingBinanceAccountClient(),
        binance_exchange_info_provider_factory=lambda _: exchange_info_provider or StaticExchangeInfoProvider(),
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


def valid_exchange_info(lot_size: BinanceQuantityFilter | None = None) -> BinanceExchangeInfo:
    return BinanceExchangeInfo(
        symbols={
            "BTCUSDT": BinanceSymbolRules(
                symbol="BTCUSDT",
                base_asset="BTC",
                quote_asset="USDT",
                status="TRADING",
                order_types=frozenset({"LIMIT", "MARKET"}),
                lot_size=lot_size,
            )
        }
    )
