import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import TextIO

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.data.schemas import MarketEvent, MarketEventType
from app.engine.bot_runner import BotRunner, RunnerConfig
from app.models.bot import Bot
from app.models.execution_profile import ExecutionProfile
from app.models.strategy import Strategy
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.execution_profile import ExecutionProfileRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.repositories.strategy import StrategyRepository
from app.services.draft_balance import DraftBalanceService
from app.services.execution_reconciliation import ExecutionReconciliationStatusService
from app.services.portfolio_account import PortfolioAccountService

SYMBOL = "BTCUSDT"
BASE_ASSET = "BTC"
QUOTE_ASSET = "USDT"
ENTRY_BELOW = Decimal("100")
EXIT_ABOVE = Decimal("110")
BUY_PRICE = Decimal("95")
SELL_PRICE = Decimal("115")
ORDER_QUANTITY = Decimal("0.1")
INITIAL_QUOTE_BALANCE = Decimal("10000")
ZERO = Decimal("0")


class CliArgumentError(Exception):
    pass


class CliRuntimeError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


@dataclass(frozen=True)
class SmokeArtifacts:
    order_id: int
    fill_id: int
    attempt_id: int


class LocalPaperMarketDataService:
    def __init__(self):
        self._latest_by_symbol: dict[str, MarketEvent] = {}

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def set_price(self, symbol: str, price: Decimal) -> MarketEvent:
        normalized_symbol = symbol.strip().upper()
        event = MarketEvent(
            provider="local-paper-demo",
            symbol=normalized_symbol,
            event_type=MarketEventType.TICKER,
            event_ts=datetime.now(timezone.utc),
            price=price,
            close=price,
        )
        self._latest_by_symbol[normalized_symbol] = event
        return event

    def get_latest(self, symbol: str | None = None):
        if symbol is None:
            return dict(self._latest_by_symbol)
        return self._latest_by_symbol.get(symbol.strip().upper())

    def get_status(self):
        return {
            "running": False,
            "enabled": True,
            "provider": "local-paper-demo",
            "symbol": SYMBOL,
            "last_received_event_ts": None,
            "last_received_at": None,
            "received_event_count": len(self._latest_by_symbol),
        }


def run_smoke(
    *,
    bot_id: int | None = None,
    session_factory=None,
    settings_provider=get_settings,
) -> dict[str, object]:
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    settings = settings_provider()
    market_data_service = LocalPaperMarketDataService()
    runner = _build_safe_runner(session_factory, market_data_service, settings)

    selected_bot_id: int | None = None
    try:
        with session_factory() as db:
            PortfolioAccountService(PortfolioRepository(db)).ensure_account(QUOTE_ASSET, INITIAL_QUOTE_BALANCE)
            bot = _select_or_create_demo_bot(db, bot_id=bot_id)
            selected_bot_id = bot.id
            _ensure_clean_start(db, bot)
            initial_balance = _reset_draft_balance(db, bot.id)
            initial_position = _paper_position_quantity(db, bot.id)
            initial_equity_count = _equity_count(db, bot.id)
            initial_attempt_count = len(
                ExecutionAttemptRepository(db).list_filtered(bot_id=bot.id, mode="paper", limit=100)
            )

        market_data_service.set_price(SYMBOL, BUY_PRICE)
        runner.resume_bot(selected_bot_id)
        buy_result = _model_dump(asyncio.run(runner.run_bot_once(selected_bot_id)))
        _expect(buy_result["action"] == "bought", f"expected BUY action, got {buy_result['action']}")
        _expect(buy_result["message"] == "buy_filled", f"expected buy_filled, got {buy_result['message']}")

        with session_factory() as db:
            buy_artifacts = _latest_side_artifacts(db, bot_id=selected_bot_id, side="buy")
            _verify_after_buy(db, bot_id=selected_bot_id, initial_balance=initial_balance)

        market_data_service.set_price(SYMBOL, SELL_PRICE)
        sell_result = _model_dump(asyncio.run(runner.run_bot_once(selected_bot_id)))
        _expect(sell_result["action"] == "sold", f"expected SELL action, got {sell_result['action']}")
        _expect(sell_result["message"] == "sell_filled", f"expected sell_filled, got {sell_result['message']}")

        with session_factory() as db:
            sell_artifacts = _latest_side_artifacts(db, bot_id=selected_bot_id, side="sell")
            final_balance = _verify_after_sell(db, bot_id=selected_bot_id, initial_balance=initial_balance)
            final_position = PaperPositionRepository(db).get_for_bot_symbol(bot_id=selected_bot_id, symbol=SYMBOL)
            final_realized_pnl = final_position.realized_pnl if final_position is not None else ZERO
            equity_count = _equity_count(db, selected_bot_id)
            attempts = ExecutionAttemptRepository(db).list_filtered(bot_id=selected_bot_id, mode="paper", limit=100)
            reconciliation = ExecutionReconciliationStatusService(ExecutionAttemptRepository(db)).get_bot_status(
                bot_id=selected_bot_id,
                limit=20,
            )
            reconciliation_jobs = ExecutionReconciliationJobRepository(db).list_for_bot(bot_id=selected_bot_id)
            latest_activity = RunEventRepository(db).list_recent_for_bot(selected_bot_id, limit=1)

            _expect(equity_count >= initial_equity_count + 2, "expected at least two new paper equity snapshots")
            _expect(len(attempts) >= initial_attempt_count + 2, "expected BUY and SELL execution attempts")
            _expect(reconciliation.recent_attempts == [], "paper smoke should not create reconciliation attempts")
            _expect(reconciliation_jobs == [], "paper smoke should not create reconciliation jobs")
            _expect(latest_activity and latest_activity[0].message == "order_filled", "latest activity is not a fill event")

        return {
            "result": "PASS",
            "mode": "local_paper_demo_only",
            "bot_id": selected_bot_id,
            "initial_balance": _decimal_string(initial_balance),
            "final_balance": _decimal_string(final_balance),
            "realized_pnl": _decimal_string(final_realized_pnl),
            "initial_position_quantity": _decimal_string(initial_position),
            "final_position_quantity": _decimal_string(final_position.quantity if final_position is not None else ZERO),
            "buy_order_id": buy_artifacts.order_id,
            "buy_fill_id": buy_artifacts.fill_id,
            "buy_execution_attempt_id": buy_artifacts.attempt_id,
            "sell_order_id": sell_artifacts.order_id,
            "sell_fill_id": sell_artifacts.fill_id,
            "sell_execution_attempt_id": sell_artifacts.attempt_id,
            "equity_snapshots_count": equity_count,
            "reconciliation_jobs_count": len(reconciliation_jobs),
            "final_bot_status": _pause_bot(session_factory, selected_bot_id),
        }
    except Exception:
        if selected_bot_id is not None:
            _pause_bot(session_factory, selected_bot_id)
        raise
    finally:
        if selected_bot_id is not None:
            _pause_bot(session_factory, selected_bot_id)


def _build_safe_runner(session_factory, market_data_service, settings: Settings) -> BotRunner:
    return BotRunner(
        session_factory=session_factory,
        market_data_service=market_data_service,
        config=RunnerConfig(
            enabled=False,
            poll_interval_seconds=settings.bot_runner_poll_interval_seconds,
            simulation_enabled=True,
            simulation_fee_bps=settings.simulation_fee_bps,
            simulation_slippage_bps=settings.simulation_slippage_bps,
            execution_global_enabled=True,
            execution_live_enabled=False,
            binance_testnet_broker_enabled=False,
            binance_testnet_order_submission_enabled=False,
            binance_testnet_dry_run_enabled=True,
            execution_max_order_notional=settings.execution_max_order_notional,
            execution_max_daily_order_count=settings.execution_max_daily_order_count,
            execution_max_daily_loss=settings.execution_max_daily_loss,
        ),
    )


def _select_or_create_demo_bot(db: Session, *, bot_id: int | None) -> Bot:
    bot_repository = BotRepository(db)
    if bot_id is not None:
        bot = bot_repository.get_by_id(bot_id)
        if bot is None:
            raise CliRuntimeError(f"bot {bot_id} was not found")
        if bot.execution_mode != "paper" or not bot.is_paper:
            raise CliRuntimeError(f"bot {bot.id} is not a paper bot")
        _configure_existing_bot_for_smoke(db, bot)
        return bot

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    strategy = Strategy(
        name=f"Local Paper Demo Smoke Strategy {suffix}",
        description="Local paper/demo smoke only; no Binance/live/testnet order submission.",
        symbol=SYMBOL,
        timeframe="1m",
        strategy_type="price_threshold",
        parameters={"buy_below": str(ENTRY_BELOW), "sell_above": str(EXIT_ABOVE), "quantity": str(ORDER_QUANTITY)},
        is_active=True,
    )
    strategy = StrategyRepository(db).create(strategy)
    bot = Bot(
        name=f"Local Paper Demo Smoke Bot {suffix}",
        strategy_id=strategy.id,
        exchange_name="Local Simulator",
        status="paused",
        is_paper=True,
        execution_mode="paper",
        notes="Local paper/demo smoke only.",
    )
    bot = bot_repository.create(bot)
    ExecutionProfileRepository(db).create(_smoke_profile(bot.id))
    return bot


def _configure_existing_bot_for_smoke(db: Session, bot: Bot) -> None:
    strategy = StrategyRepository(db).get_by_id(bot.strategy_id)
    if strategy is None:
        raise CliRuntimeError(f"strategy {bot.strategy_id} for bot {bot.id} was not found")
    strategy.symbol = SYMBOL
    strategy.timeframe = "1m"
    strategy.strategy_type = "price_threshold"
    strategy.parameters = {"buy_below": str(ENTRY_BELOW), "sell_above": str(EXIT_ABOVE), "quantity": str(ORDER_QUANTITY)}
    strategy.is_active = True
    StrategyRepository(db).update(strategy)

    profile_repository = ExecutionProfileRepository(db)
    profile = profile_repository.get_by_bot_id(bot.id)
    if profile is None:
        profile_repository.create(_smoke_profile(bot.id))
    else:
        profile.strategy_type = "price_threshold"
        profile.entry_below = ENTRY_BELOW
        profile.exit_above = EXIT_ABOVE
        profile.order_quantity = ORDER_QUANTITY
        profile.default_order_type = "market"
        profile.is_enabled = True
        profile_repository.update(profile)

    bot.status = "paused"
    bot.is_paper = True
    bot.execution_mode = "paper"
    BotRepository(db).update(bot)


def _smoke_profile(bot_id: int) -> ExecutionProfile:
    return ExecutionProfile(
        bot_id=bot_id,
        max_position_size_usd=10000,
        max_daily_loss_usd=1000,
        max_open_positions=1,
        strategy_type="price_threshold",
        entry_below=ENTRY_BELOW,
        exit_above=EXIT_ABOVE,
        order_quantity=ORDER_QUANTITY,
        cooldown_seconds=60,
        default_order_type="market",
        is_enabled=True,
    )


def _ensure_clean_start(db: Session, bot: Bot) -> None:
    quantity = _paper_position_quantity(db, bot.id)
    if quantity != ZERO:
        raise CliRuntimeError(f"bot {bot.id} has open paper position quantity {quantity}; refusing non-clean smoke")


def _reset_draft_balance(db: Session, bot_id: int) -> Decimal:
    snapshot = DraftBalanceService(DraftBalanceRepository(db), BotRepository(db)).reset_bot_draft_balance(
        bot_id,
        defaults={QUOTE_ASSET: (INITIAL_QUOTE_BALANCE, ZERO), BASE_ASSET: (ZERO, ZERO)},
    )
    return _asset_available(snapshot.assets, QUOTE_ASSET)


def _verify_after_buy(db: Session, *, bot_id: int, initial_balance: Decimal) -> None:
    quote_balance = _current_quote_balance(db, bot_id)
    position = PaperPositionRepository(db).get_for_bot_symbol(bot_id=bot_id, symbol=SYMBOL)
    _expect(quote_balance < initial_balance, "Draft Balance did not decrease after BUY")
    _expect(position is not None and position.quantity > ZERO, "Paper Position did not open after BUY")
    _expect(_equity_count(db, bot_id) >= 1, "Paper Equity snapshot was not created after BUY")


def _verify_after_sell(db: Session, *, bot_id: int, initial_balance: Decimal) -> Decimal:
    quote_balance = _current_quote_balance(db, bot_id)
    position = PaperPositionRepository(db).get_for_bot_symbol(bot_id=bot_id, symbol=SYMBOL)
    _expect(quote_balance > initial_balance, "Draft Balance did not increase above initial balance after SELL")
    _expect(position is not None and position.quantity == ZERO, "Paper Position did not close after SELL")
    _expect(position.realized_pnl > ZERO, "Paper Position realized PnL did not increase after SELL")
    return quote_balance


def _latest_side_artifacts(db: Session, *, bot_id: int, side: str) -> SmokeArtifacts:
    orders = PortfolioRepository(db).list_orders_filtered(bot_id=bot_id, mode="paper", side=side, limit=1)
    _expect(len(orders) == 1, f"expected latest {side} paper order")
    order = orders[0]
    _expect(order.status == "filled", f"expected filled {side} paper order")
    fills = PortfolioRepository(db).list_fills_for_order(order.id)
    _expect(len(fills) == 1, f"expected one {side} paper fill")
    attempts = ExecutionAttemptRepository(db).list_filtered(bot_id=bot_id, mode="paper", side=side, limit=1)
    _expect(len(attempts) == 1, f"expected one {side} execution attempt")
    _expect(attempts[0].order_id == order.id, f"{side} execution attempt is not linked to the order")
    _expect(attempts[0].final_status == "filled", f"expected filled {side} execution attempt")
    return SmokeArtifacts(order_id=order.id, fill_id=fills[0].id, attempt_id=attempts[0].id)


def _pause_bot(session_factory, bot_id: int) -> str:
    with session_factory() as db:
        bot = BotRepository(db).get_by_id(bot_id)
        if bot is None:
            return "missing"
        bot.status = "paused"
        BotRepository(db).update(bot)
        return bot.status


def _paper_position_quantity(db: Session, bot_id: int) -> Decimal:
    position = PaperPositionRepository(db).get_for_bot_symbol(bot_id=bot_id, symbol=SYMBOL)
    return position.quantity if position is not None else ZERO


def _current_quote_balance(db: Session, bot_id: int) -> Decimal:
    rows = DraftBalanceRepository(db).list_for_bot(bot_id)
    return _asset_available(rows, QUOTE_ASSET)


def _asset_available(assets, asset: str) -> Decimal:
    for row in assets:
        if row.asset == asset:
            return row.available
    raise CliRuntimeError(f"draft balance asset {asset} was not found")


def _equity_count(db: Session, bot_id: int) -> int:
    return len(PaperEquitySnapshotRepository(db).list_latest_for_bot(bot_id=bot_id, limit=100))


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise CliRuntimeError(message)


def _model_dump(value) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _decimal_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


def main(
    argv: list[str] | None = None,
    *,
    session_factory=None,
    settings_provider=get_settings,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = run_smoke(
            bot_id=args.bot_id,
            session_factory=session_factory,
            settings_provider=settings_provider,
        )
    except CliArgumentError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    except SystemExit as exc:
        return int(exc.code or 0)
    except CliRuntimeError as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=stdout)
        return 1
    except Exception:
        print(json.dumps({"result": "FAIL", "error": "local paper demo smoke failed"}, sort_keys=True), file=stdout)
        return 1

    print(json.dumps(summary, sort_keys=True), file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="run-local-paper-demo-smoke",
        description="Run a local paper/demo-only BUY/SELL smoke. Does not enable Binance, testnet, or live orders.",
    )
    parser.add_argument("--bot-id", type=_positive_int, help="existing paper bot id to use instead of creating one")
    return parser


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bot id must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("bot id must be greater than zero")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
