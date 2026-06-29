import json
from io import StringIO

from app.cli import run_local_paper_demo_smoke as cli
from app.core.config import Settings
from app.repositories.bot import BotRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.binance import BinanceTestnetBroker


def test_local_paper_demo_smoke_creates_buy_sell_artifacts_and_pauses_bot(db_session_factory, monkeypatch) -> None:
    def fail_if_binance_submission_is_touched(self, intent):
        raise AssertionError("local paper demo smoke must not touch Binance testnet order submission")

    monkeypatch.setattr(BinanceTestnetBroker, "submit_market_order", fail_if_binance_submission_is_touched)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        [],
        session_factory=db_session_factory,
        settings_provider=lambda: Settings(_env_file=None),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    summary = json.loads(stdout.getvalue())
    assert summary["result"] == "PASS"
    assert summary["mode"] == "local_paper_demo_only"
    assert summary["initial_balance"] == "10000"
    assert summary["final_balance"] > summary["initial_balance"]
    assert summary["realized_pnl"] > "0"
    assert summary["buy_order_id"] != summary["sell_order_id"]
    assert summary["buy_fill_id"] != summary["sell_fill_id"]
    assert summary["buy_execution_attempt_id"] != summary["sell_execution_attempt_id"]
    assert summary["equity_snapshots_count"] == 2
    assert summary["reconciliation_jobs_count"] == 0
    assert summary["final_bot_status"] == "paused"

    with db_session_factory() as session:
        bot = BotRepository(session).get_by_id(summary["bot_id"])
        assert bot is not None
        assert bot.status == "paused"
        assert bot.is_paper is True
        assert bot.execution_mode == "paper"

        orders = PortfolioRepository(session).list_orders_filtered(bot_id=bot.id, mode="paper", limit=10)
        attempts = ExecutionAttemptRepository(session).list_filtered(bot_id=bot.id, mode="paper", limit=10)
        position = PaperPositionRepository(session).get_for_bot_symbol(bot_id=bot.id, symbol="BTCUSDT")
        snapshots = PaperEquitySnapshotRepository(session).list_latest_for_bot(bot_id=bot.id, limit=10)

        assert [order.side for order in orders] == ["sell", "buy"]
        assert all(order.status == "filled" for order in orders)
        assert [attempt.side for attempt in attempts] == ["sell", "buy"]
        assert all(attempt.broker == "paper" for attempt in attempts)
        assert position is not None
        assert position.quantity == 0
        assert position.realized_pnl > 0
        assert [snapshot.event_type for snapshot in snapshots] == ["sell_fill", "buy_fill"]
        assert ExecutionReconciliationJobRepository(session).list_for_bot(bot_id=bot.id) == []


def test_local_paper_demo_smoke_refuses_non_paper_selected_bot(
    db_session,
    db_session_factory,
    bot_stack_factory,
) -> None:
    _, bot, _ = bot_stack_factory(
        db_session,
        status="active",
        is_paper=False,
        execution_mode="live",
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        ["--bot-id", str(bot.id)],
        session_factory=db_session_factory,
        settings_provider=lambda: Settings(_env_file=None),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == {
        "error": f"bot {bot.id} is not a paper bot",
        "result": "FAIL",
    }
    assert PortfolioRepository(db_session).list_orders_filtered(bot_id=bot.id, mode="paper") == []
    assert ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper", limit=10) == []
