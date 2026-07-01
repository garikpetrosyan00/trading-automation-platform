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
    assert "recommendation" in result["checked_fields"]
    assert "executive_summary" in result["checked_fields"]


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


def test_validate_backtest_comparison_report_rejects_invalid_score_fields(tmp_path) -> None:
    report = valid_report()
    report["runs"][0]["overall_score"] = "not-a-number"
    report["runs"][1]["score_components"]["return_score"] = "not-a-number"
    report["runs"][1]["score_warnings"] = ["too_few_trades", 123]
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "runs[0].overall_score must be numeric" in result["errors"]
    assert "runs[1].score_components.return_score must be numeric" in result["errors"]
    assert "runs[1].score_warnings must be a list of strings" in result["errors"]


def test_validate_backtest_comparison_report_rejects_invalid_recommendation_fields(tmp_path) -> None:
    report = valid_report()
    report["recommendation"]["recommendation_status"] = "maybe"
    report["recommendation"]["recommended_run"]["overall_score"] = "not-a-number"
    report["recommendation"]["recommended_run"]["run_name"] = "missing"
    report["recommendation"]["recommendation_reason"]["highest_overall_score"] = "yes"
    report["recommendation"]["recommendation_warnings"] = ["all_runs_weak", 123]
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "recommendation.recommendation_status is invalid" in result["errors"]
    assert "recommendation.recommended_run.overall_score must be numeric" in result["errors"]
    assert "recommendation.recommended_run.run_name references unknown run: missing" in result["errors"]
    assert "recommendation.recommendation_reason.highest_overall_score must be boolean" in result["errors"]
    assert "recommendation.recommendation_warnings must be a list of strings" in result["errors"]


def test_validate_backtest_comparison_report_rejects_invalid_acceptance_fields(tmp_path) -> None:
    report = valid_report()
    report["recommendation"]["acceptance_status"] = "maybe"
    report["recommendation"]["acceptance_gates"][0]["passed"] = "yes"
    report["recommendation"]["acceptance_gates"][0]["severity"] = "note"
    report["recommendation"]["acceptance_gates"][0]["actual"] = float("nan")
    report["recommendation"]["acceptance_failures"] = ["too_few_trades", 123]
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "recommendation.acceptance_status is invalid" in result["errors"]
    assert "recommendation.acceptance_gates[0].passed must be boolean" in result["errors"]
    assert "recommendation.acceptance_gates[0].severity is invalid" in result["errors"]
    assert "recommendation.acceptance_gates[0].actual must be finite" in result["errors"]
    assert "recommendation.acceptance_failures must be a list of strings" in result["errors"]


def test_validate_backtest_comparison_report_rejects_invalid_executive_summary_fields(tmp_path) -> None:
    report = valid_report()
    report["executive_summary"]["decision"] = "maybe"
    report["executive_summary"]["acceptance_status"] = "maybe"
    report["executive_summary"]["recommendation_status"] = "maybe"
    report["executive_summary"]["next_action"] = "maybe"
    report["executive_summary"]["overall_score"] = "not-a-number"
    report["executive_summary"]["key_strengths"] = ["positive_return", 123]
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 1
    assert "executive_summary.decision is invalid" in result["errors"]
    assert "executive_summary.acceptance_status is invalid" in result["errors"]
    assert "executive_summary.recommendation_status is invalid" in result["errors"]
    assert "executive_summary.next_action is invalid" in result["errors"]
    assert "executive_summary.overall_score must be numeric" in result["errors"]
    assert "executive_summary.key_strengths must be a list of strings" in result["errors"]


def test_validate_backtest_comparison_report_accepts_older_report_without_recommendation(tmp_path) -> None:
    report = valid_report()
    report.pop("recommendation")
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 0
    assert result["valid"] is True


def test_validate_backtest_comparison_report_accepts_older_report_without_executive_summary(tmp_path) -> None:
    report = valid_report()
    report.pop("executive_summary")
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 0
    assert result["valid"] is True


def test_validate_backtest_comparison_report_accepts_recommendation_without_acceptance_fields(tmp_path) -> None:
    report = valid_report()
    report["recommendation"].pop("acceptance_status")
    report["recommendation"].pop("acceptance_gates")
    report["recommendation"].pop("acceptance_failures")
    report["recommendation"].pop("acceptance_warnings")
    report_path = write_report(tmp_path, report)

    exit_code, result = run_validator(report_path)

    assert exit_code == 0
    assert result["valid"] is True


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
        "ranking_metrics": ["overall_score", "total_return", "ending_balance", "max_drawdown_pct"],
        "runs": [
            {
                "run_name": "base",
                "run_path": "base",
                "overall_score": "60",
                "score_components": {
                    "return_score": "41",
                    "drawdown_score": "95.8333",
                    "profit_factor_score": "100",
                    "win_rate_score": "100",
                    "trade_count_score": "10",
                    "exposure_score": "100",
                    "final_normalized_score": "60",
                },
                "score_warnings": ["too_few_trades", "infinite_or_unavailable_profit_factor"],
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
                    "overall_score": "60",
                },
            },
            {
                "run_name": "candidate",
                "run_path": "candidate",
                "overall_score": "61",
                "score_components": {
                    "return_score": "42",
                    "drawdown_score": "98.3333",
                    "profit_factor_score": "100",
                    "win_rate_score": "100",
                    "trade_count_score": "10",
                    "exposure_score": "100",
                    "final_normalized_score": "61",
                },
                "score_warnings": ["too_few_trades", "infinite_or_unavailable_profit_factor"],
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
                    "overall_score": "61",
                },
            },
        ],
        "rankings": {
            "overall_score": [
                {
                    "rank": 1,
                    "run_name": "candidate",
                    "run_path": "candidate",
                    "metric": "overall_score",
                    "value": "61",
                    "available": True,
                },
                {
                    "rank": 2,
                    "run_name": "base",
                    "run_path": "base",
                    "metric": "overall_score",
                    "value": "60",
                    "available": True,
                },
            ],
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
        "recommendation": {
            "recommended_run": {
                "strategy": "moving_average_crossover",
                "run_name": "candidate",
                "run_path": "candidate",
                "overall_score": "61",
                "total_return_pct": None,
                "max_drawdown_pct": "0.5",
                "max_drawdown_amount": "50",
                "profit_factor": None,
                "win_rate": "100",
                "trade_count": 1,
                "exposure_pct": "50",
                "score_warnings": ["too_few_trades", "infinite_or_unavailable_profit_factor"],
            },
            "recommendation_status": "weak_recommendation",
            "recommendation_reason": {
                "highest_overall_score": True,
                "positive_return": True,
                "acceptable_drawdown": True,
                "sufficient_trades": False,
                "better_risk_adjusted_profile": True,
                "score_gap_to_runner_up": "1",
            },
            "recommendation_warnings": [
                "all_runs_weak",
                "best_run_has_too_few_trades",
                "infinite_or_unavailable_profit_factor",
                "too_few_trades",
            ],
            "acceptance_status": "rejected",
            "acceptance_gates": [
                {
                    "name": "minimum_overall_score",
                    "passed": False,
                    "actual": "61",
                    "threshold": "70",
                    "severity": "failure",
                    "reason": "overall_score must be at least 70",
                },
                {
                    "name": "weak_recommendation_only",
                    "passed": True,
                    "actual": "weak_recommendation",
                    "threshold": "recommended",
                    "severity": "warning",
                    "reason": "best run is only weakly recommended",
                },
            ],
            "acceptance_failures": ["score_below_minimum", "too_few_trades"],
            "acceptance_warnings": ["weak_recommendation_only"],
            "runner_up_runs": [
                {
                    "strategy": "price_threshold",
                    "run_name": "base",
                    "run_path": "base",
                    "overall_score": "60",
                    "total_return_pct": None,
                    "max_drawdown_pct": "1.25",
                    "max_drawdown_amount": "125",
                    "profit_factor": None,
                    "win_rate": "100",
                    "trade_count": 1,
                    "exposure_pct": "50",
                    "score_warnings": ["too_few_trades", "infinite_or_unavailable_profit_factor"],
                }
            ],
        },
        "executive_summary": {
            "title": "Local Backtest Comparison Executive Summary",
            "decision": "reject_candidate",
            "best_strategy": "moving_average_crossover",
            "best_run_label": "candidate",
            "acceptance_status": "rejected",
            "recommendation_status": "weak_recommendation",
            "overall_score": "61",
            "key_strengths": ["highest_overall_score", "positive_return", "acceptable_drawdown"],
            "key_risks": ["too_few_trades", "low_score", "weak_recommendation_only"],
            "next_action": "reject_or_adjust_strategy",
            "summary_text": (
                "Decision reject_candidate for candidate; acceptance_status=rejected; "
                "recommendation_status=weak_recommendation; next_action=reject_or_adjust_strategy."
            ),
        },
        "safety_note": (
            "Local backtest artifact comparison report only; no live/testnet/Binance calls, "
            "DB writes, orders, fills, execution attempts, reconciliation jobs, or paper/live execution."
        ),
    }
