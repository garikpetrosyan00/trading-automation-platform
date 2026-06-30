import json
from io import StringIO

from app.cli import validate_backtest_comparison_report as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def test_validate_backtest_comparison_report_accepts_valid_report(tmp_path) -> None:
    report_path = write_report(tmp_path, valid_report())
    stdout = StringIO()

    exit_code = cli.main(["--report-json", str(report_path)], stdout=stdout)

    assert exit_code == 0
    result = json.loads(stdout.getvalue())
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["warnings"] == []
    assert "generated_at" in result["checked_fields"]
    assert "run_summaries" in result["checked_fields"]
    assert "ranking_references" in result["checked_fields"]


def test_validate_backtest_comparison_report_reports_missing_required_fields(tmp_path) -> None:
    report = valid_report()
    report.pop("generated_at")
    report.pop("safety_note")
    report_path = write_report(tmp_path, report)
    stdout = StringIO()

    exit_code = cli.main(["--report-json", str(report_path)], stdout=stdout)

    assert exit_code == 1
    result = json.loads(stdout.getvalue())
    assert result["valid"] is False
    assert "missing required field: generated_at" in result["errors"]
    assert "missing required field: safety_note" in result["errors"]


def test_validate_backtest_comparison_report_rejects_mismatched_run_count(tmp_path) -> None:
    report = valid_report()
    report["run_count"] = 3
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "run_count does not match runs length" in result["errors"]


def test_validate_backtest_comparison_report_rejects_invalid_ranking_reference(tmp_path) -> None:
    report = valid_report()
    report["rankings"]["total_return"][0]["run_name"] = "missing"
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "rankings.total_return[0] references unknown run: missing" in result["errors"]


def test_validate_backtest_comparison_report_rejects_unsafe_absolute_path(tmp_path) -> None:
    report = valid_report()
    report["runs"][0]["run_path"] = str(tmp_path / "runs" / "base")
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "runs[0].run_path must not expose an absolute path" in result["errors"]


def test_validate_backtest_comparison_report_can_allow_absolute_paths(tmp_path) -> None:
    report = valid_report()
    report["runs"][0]["run_path"] = str(tmp_path / "runs" / "base")
    report_path = write_report(tmp_path, report)
    stdout = StringIO()

    exit_code = cli.main(["--report-json", str(report_path), "--allow-absolute-paths"], stdout=stdout)

    assert exit_code == 0
    assert json.loads(stdout.getvalue())["valid"] is True


def test_validate_backtest_comparison_report_rejects_invalid_metric_type(tmp_path) -> None:
    report = valid_report()
    report["runs"][0]["summary"]["total_return"] = "not-a-number"
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "runs[0].summary.total_return must be numeric" in result["errors"]


def test_validate_backtest_comparison_report_rejects_invalid_ranking_metric_value(tmp_path) -> None:
    report = valid_report()
    report["rankings"]["total_return"][0]["value"] = "not-a-number"
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "rankings.total_return[0].value must be numeric when available" in result["errors"]


def test_validate_backtest_comparison_report_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    report_path = write_report(tmp_path, valid_report())

    assert cli.main(["--report-json", str(report_path)], stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def run_validator(report_path):
    stdout = StringIO()
    exit_code = cli.main(["--report-json", str(report_path)], stdout=stdout)
    return exit_code, json.loads(stdout.getvalue())


def write_report(tmp_path, report: dict):
    path = tmp_path / "comparison_report.json"
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return path


def valid_report() -> dict:
    return {
        "result": "PASS",
        "generated_at": "2026-07-01T00:00:00Z",
        "run_count": 2,
        "ranking_metrics": ["total_return", "ending_balance", "max_drawdown_pct"],
        "runs": [
            {
                "run_name": "base",
                "run_path": "base",
                "summary": {
                    "run_name": "base",
                    "strategy_type": "price_threshold",
                    "entry_below": "95",
                    "exit_above": "105",
                    "starting_balance": "10000",
                    "ending_balance": "10050",
                    "total_return": "50",
                    "trades_count": 2,
                    "completed_round_trips": 1,
                    "win_count": 1,
                    "loss_count": 0,
                    "breakeven_count": 0,
                    "win_rate_pct": "100",
                    "average_winning_trade_pnl": "50",
                    "average_losing_trade_pnl": None,
                    "average_trade_pnl": "50",
                    "best_trade_pnl": "50",
                    "worst_trade_pnl": "50",
                    "profit_factor": None,
                    "max_drawdown_amount": "125",
                    "max_drawdown_pct": "1.25",
                    "exposure_pct": "50",
                },
            },
            {
                "run_name": "candidate",
                "run_path": "candidate",
                "summary": {
                    "run_name": "candidate",
                    "strategy_type": "moving_average_crossover",
                    "fast_window": "2",
                    "slow_window": "3",
                    "starting_balance": "10000",
                    "ending_balance": "10100",
                    "total_return": "100",
                    "trades_count": 2,
                    "completed_round_trips": 1,
                    "win_count": 1,
                    "loss_count": 0,
                    "breakeven_count": 0,
                    "win_rate_pct": "100",
                    "average_winning_trade_pnl": "100",
                    "average_losing_trade_pnl": None,
                    "average_trade_pnl": "100",
                    "best_trade_pnl": "100",
                    "worst_trade_pnl": "100",
                    "profit_factor": None,
                    "max_drawdown_amount": "50",
                    "max_drawdown_pct": "0.5",
                    "exposure_pct": "50",
                },
            },
        ],
        "rankings": {
            "total_return": [
                {
                    "rank": 1,
                    "run_name": "candidate",
                    "run_path": "candidate",
                    "metric": "total_return",
                    "value": "100",
                    "available": True,
                },
                {
                    "rank": 2,
                    "run_name": "base",
                    "run_path": "base",
                    "metric": "total_return",
                    "value": "50",
                    "available": True,
                },
            ],
            "ending_balance": [],
            "max_drawdown_pct": [],
        },
        "safety_note": (
            "Local backtest artifact comparison report only; no live/testnet/Binance calls, "
            "DB writes, orders, fills, execution attempts, reconciliation jobs, or paper/live execution."
        ),
    }
