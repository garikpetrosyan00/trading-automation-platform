import json
from decimal import Decimal
from io import StringIO

from app.cli import run_bot_runner_once as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository


def test_cli_missing_bot_returns_safe_nonzero_without_running(db_session_factory) -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        ["--bot-id", "999999"],
        session_factory=db_session_factory,
        runner_factory=fail_if_runner_built,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue().strip() == "error: bot 999999 was not found"


def test_cli_refuses_testnet_or_live_bot_by_default(db_session, db_session_factory, bot_stack_factory) -> None:
    _, testnet_bot, _ = bot_stack_factory(
        db_session,
        status="active",
        is_paper=False,
        execution_mode="testnet",
    )
    _, live_bot, _ = bot_stack_factory(
        db_session,
        name="Live Bot",
        status="active",
        is_paper=False,
        execution_mode="live",
    )

    for bot in (testnet_bot, live_bot):
        stdout = StringIO()
        stderr = StringIO()
        exit_code = cli.main(
            ["--bot-id", str(bot.id)],
            session_factory=db_session_factory,
            runner_factory=fail_if_runner_built,
            stdout=stdout,
            stderr=stderr,
        )

        assert exit_code == 1
        assert stdout.getvalue() == ""
        assert stderr.getvalue().strip() == f"error: bot {bot.id} is not a paper bot"


def test_cli_paused_paper_bot_is_skipped_without_artifacts_or_reconciliation(
    db_session,
    db_session_factory,
    bot_stack_factory,
    bot_runner_factory,
    funded_account,
    reset_draft_balance_for_bot,
) -> None:
    funded_account(db_session, currency="USDT", amount=Decimal("10000"))
    _, bot, _ = bot_stack_factory(db_session, status="paused")
    reset_draft_balance_for_bot(db_session, bot.id)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        ["--bot-id", str(bot.id)],
        session_factory=db_session_factory,
        runner_factory=lambda _session_factory: bot_runner_factory(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    summary = json.loads(stdout.getvalue())
    assert summary == {
        "action": "bot_paused",
        "bot_id": bot.id,
        "executed": False,
        "execution_attempts_created": 0,
        "execution_mode": "paper",
        "paper_fills_created": 0,
        "paper_orders_created": 0,
        "record_noop_events": False,
        "result": "skipped",
        "skipped": True,
        "status": "paused",
    }
    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_for_bot(bot_id=bot.id) == []


def test_cli_active_paper_bot_evaluates_existing_runner_path_with_local_market_data(
    db_session,
    db_session_factory,
    bot_stack_factory,
    bot_runner_factory,
    funded_account,
    reset_draft_balance_for_bot,
    set_latest_market_price,
) -> None:
    funded_account(db_session, currency="USDT", amount=Decimal("10000"))
    _, bot, _ = bot_stack_factory(db_session, status="active")
    reset_draft_balance_for_bot(db_session, bot.id)
    set_latest_market_price("95")
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        ["--bot-id", str(bot.id)],
        session_factory=db_session_factory,
        runner_factory=lambda _session_factory: bot_runner_factory(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    summary = json.loads(stdout.getvalue())
    assert summary["bot_id"] == bot.id
    assert summary["execution_mode"] == "paper"
    assert summary["status"] == "active"
    assert summary["result"] == "evaluated"
    assert summary["action"] == "paper_order_created"
    assert summary["executed"] is True
    assert summary["skipped"] is False
    assert summary["paper_orders_created"] == 1
    assert summary["paper_fills_created"] == 1
    assert summary["execution_attempts_created"] == 1

    orders = PortfolioRepository(db_session).list_orders_filtered(bot_id=bot.id, mode="paper")
    attempts = ExecutionAttemptRepository(db_session).list_filtered(bot_id=bot.id, mode="paper", limit=10)
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].status == "filled"
    assert len(attempts) == 1
    assert attempts[0].broker == "paper"
    assert attempts[0].final_status == "filled"
    assert ExecutionReconciliationJobRepository(db_session).list_for_bot(bot_id=bot.id) == []


def fail_if_runner_built(_session_factory):
    raise AssertionError("runner must not be built")
