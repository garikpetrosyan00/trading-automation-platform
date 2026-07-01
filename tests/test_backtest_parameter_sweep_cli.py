import csv
import json
from io import StringIO

import pytest

from app.cli import run_backtest_parameter_sweep as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.backtest_parameter_sweep import build_sweep_scoring_summary
from app.services.backtest_run_comparison import build_backtest_executive_summary, build_backtest_recommendation_summary


def test_backtest_parameter_sweep_writes_outputs_and_per_run_artifacts(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir), stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"] == "PASS"
    assert payload["combinations_count"] == 4
    assert payload["ranking_metric"] == "final_equity"
    assert "not a profitability guarantee" in payload["profitability_note"]
    assert payload["sweep_summary"]["best_parameter_set"]["parameters"] == {
        "entry_below": "95",
        "exit_above": "107",
        "order_quantity": "1",
    }
    assert payload["sweep_summary"]["best_overall_score"] == "60"
    assert payload["sweep_summary"]["recommendation_status"] == "weak_recommendation"
    assert payload["sweep_summary"]["acceptance_status"] == "rejected"
    assert payload["sweep_summary"]["executive_decision"] == "reject_candidate"
    assert payload["sweep_summary"]["tested_parameter_count"] == 4
    assert payload["sweep_summary"]["accepted_count"] == 0
    assert payload["sweep_summary"]["rejected_count"] == 4
    assert payload["sweep_summary"]["warning_count"] == 3
    assert payload["sweep_summary"]["warnings"] == [
        "all_parameter_sets_rejected",
        "best_parameter_set_has_warnings",
        "no_accepted_parameter_sets",
    ]
    assert payload["lifecycle_closeout"] == {
        "acceptance_status": "rejected",
        "best_overall_score_exists": True,
        "executive_decision": "reject_candidate",
        "recommendation_status": "weak_recommendation",
        "sweep_report_exists": True,
        "sweep_results_exists": True,
        "sweep_summary_exists": True,
        "tested_parameter_count": 4,
        "validation_status": "passed",
    }
    assert [item["parameters"] for item in payload["sweep_summary"]["top_parameter_sets"]] == [
        {"entry_below": "95", "exit_above": "107", "order_quantity": "1"},
        {"entry_below": "95", "exit_above": "105", "order_quantity": "1"},
        {"entry_below": "105", "exit_above": "107", "order_quantity": "1"},
    ]
    assert (output_dir / "sweep_summary.json").exists()
    assert (output_dir / "sweep_results.csv").exists()
    assert (output_dir / "sweep_report.md").exists()
    run_dirs = sorted(path.name for path in output_dir.iterdir() if path.is_dir())
    assert run_dirs == [
        "run_001_entry_95_exit_105",
        "run_002_entry_95_exit_107",
        "run_003_entry_105_exit_105",
        "run_004_entry_105_exit_107",
    ]
    assert all((output_dir / run_dir / "summary.json").exists() for run_dir in run_dirs)
    assert all((output_dir / run_dir / "trades.csv").exists() for run_dir in run_dirs)
    assert all((output_dir / run_dir / "equity_curve.csv").exists() for run_dir in run_dirs)


def test_backtest_parameter_sweep_multiple_combinations_and_deterministic_ranking(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"

    assert cli.main(base_args(path, output_dir), stdout=StringIO()) == 0

    summary = json.loads((output_dir / "sweep_summary.json").read_text(encoding="utf-8"))
    ranked = summary["results"]
    assert [row["rank"] for row in ranked] == [1, 2, 3, 4]
    assert ranked[0]["entry_below"] == "95"
    assert ranked[0]["exit_above"] == "107"
    assert ranked[0]["final_equity"] == "10017"
    assert ranked[0]["overall_score"] == "60"
    assert ranked[0]["acceptance_status"] == "rejected"
    assert ranked[0]["score_warnings"] == "infinite_or_unavailable_profit_factor,too_few_trades"
    assert ranked[-1]["entry_below"] == "105"
    assert ranked[-1]["exit_above"] == "105"
    assert ranked[-1]["final_equity"] == "10006"


def test_backtest_parameter_sweep_invalid_csv_path_fails_cleanly(tmp_path) -> None:
    missing_path = tmp_path / "missing.csv"
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(missing_path, output_dir), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"CSV file does not exist: {missing_path}",
        "result": "FAIL",
    }


@pytest.mark.parametrize(
    ("extra_args", "expected_error"),
    [
        (["--entry-below-values", "95,not-a-number"], "entry-below-values must be a decimal"),
        (["--entry-below-values", "95,"], "entry-below-values must be a comma-separated decimal list"),
        (["--exit-above-values", "0"], "exit-above-values values must be positive"),
        (["--strategy-type", "moving_average_cross"], "unsupported strategy type: moving_average_cross"),
    ],
)
def test_backtest_parameter_sweep_invalid_values_fail_cleanly(tmp_path, extra_args, expected_error) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(replace_args(base_args(path, output_dir), extra_args), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {"error": expected_error, "result": "FAIL"}


def test_backtest_parameter_sweep_refuses_non_empty_output_without_overwrite(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output directory is not empty; pass --overwrite to replace: {output_dir}",
        "result": "FAIL",
    }
    assert (output_dir / "old.txt").exists()


def test_backtest_parameter_sweep_overwrite_rebuilds_output(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(base_args(path, output_dir) + ["--overwrite"], stdout=StringIO())

    assert exit_code == 0
    assert not (output_dir / "old.txt").exists()
    assert (output_dir / "sweep_summary.json").exists()


def test_backtest_parameter_sweep_results_csv_and_compact_stdout(tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"
    stdout = StringIO()

    exit_code = cli.main(base_args(path, output_dir) + ["--compact"], stdout=stdout)

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed["result"] == "PASS"
    assert printed["symbol"] == "BTCUSDT"
    assert printed["timeframe"] == "1h"
    assert printed["strategy_type"] == "price_threshold"
    assert printed["combinations_count"] == 4
    assert printed["ranking_metric"] == "final_equity"
    assert printed["best_result"]["entry_below"] == "95"
    assert printed["best_result"]["exit_above"] == "107"
    assert printed["best_result"]["overall_score"] == "60"
    assert printed["best_result"]["acceptance_status"] == "rejected"
    assert printed["best_result"]["summary_path"] == str(output_dir / "run_002_entry_95_exit_107" / "summary.json")
    assert printed["sweep_summary"]["best_overall_score"] == "60"
    assert printed["sweep_summary"]["accepted_count"] == 0
    assert printed["sweep_summary"]["rejected_count"] == 4
    assert printed["lifecycle_closeout"] == {
        "acceptance_status": "rejected",
        "best_overall_score_exists": True,
        "executive_decision": "reject_candidate",
        "recommendation_status": "weak_recommendation",
        "sweep_report_exists": True,
        "sweep_results_exists": True,
        "sweep_summary_exists": True,
        "tested_parameter_count": 4,
        "validation_status": "passed",
    }
    with (output_dir / "sweep_results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["rank"] == "1"
    assert rows[0]["run_name"] == "run_002_entry_95_exit_107"
    assert rows[0]["final_equity"] == "10017"
    assert rows[0]["overall_score"] == "60"
    assert rows[0]["acceptance_status"] == "rejected"
    assert rows[0]["score_warnings"] == "infinite_or_unavailable_profit_factor,too_few_trades"


def test_sweep_scoring_summary_selects_best_by_overall_score_and_counts_acceptance() -> None:
    comparison = fake_comparison(
        [
            fake_run("middle", score="72", total_return_pct="5", entry_below="100", exit_above="110"),
            fake_run("best", score="81", total_return_pct="4", entry_below="95", exit_above="108"),
            fake_run("rejected", score="50", total_return_pct="-1", entry_below="90", exit_above="106", warnings=["negative_return"]),
        ]
    )

    summary = build_sweep_scoring_summary(comparison)

    assert summary["best_parameter_set"]["parameters"] == {
        "entry_below": "95",
        "exit_above": "108",
        "order_quantity": "1",
    }
    assert summary["best_overall_score"] == "81"
    assert summary["accepted_count"] == 2
    assert summary["rejected_count"] == 1
    assert summary["tested_parameter_count"] == 3
    assert summary["top_parameter_sets"][0]["overall_score"] == "81"


def test_sweep_scoring_summary_all_rejected_warns() -> None:
    comparison = fake_comparison(
        [
            fake_run("no_trades_a", score="20", total_return_pct="0", entry_below="90", exit_above="100", completed_round_trips=0, warnings=["no_trades"]),
            fake_run("no_trades_b", score="20", total_return_pct="0", entry_below="91", exit_above="101", completed_round_trips=0, warnings=["no_trades"]),
        ]
    )

    summary = build_sweep_scoring_summary(comparison)

    assert summary["accepted_count"] == 0
    assert summary["rejected_count"] == 2
    assert summary["warnings"] == [
        "all_parameter_sets_rejected",
        "best_parameter_set_has_warnings",
        "no_accepted_parameter_sets",
    ]


def test_sweep_scoring_summary_handles_no_tested_parameter_sets() -> None:
    summary = build_sweep_scoring_summary({"runs": []})

    assert summary == {
        "acceptance_status": "not_evaluated",
        "accepted_count": 0,
        "best_overall_score": None,
        "best_parameter_set": None,
        "executive_decision": "no_decision",
        "recommendation_status": "no_valid_runs",
        "rejected_count": 0,
        "tested_parameter_count": 0,
        "top_parameter_sets": [],
        "warning_count": 1,
        "warnings": ["no_parameter_sets_tested"],
    }


def test_sweep_scoring_summary_top_parameter_sets_use_deterministic_tie_breakers() -> None:
    comparison = fake_comparison(
        [
            fake_run("later", score="80", total_return_pct="3", entry_below="101", exit_above="111"),
            fake_run("earlier", score="80", total_return_pct="3", entry_below="100", exit_above="111"),
            fake_run("lower_return", score="80", total_return_pct="2", entry_below="99", exit_above="110"),
        ]
    )

    summary = build_sweep_scoring_summary(comparison)

    assert [item["parameters"]["entry_below"] for item in summary["top_parameter_sets"]] == ["100", "101", "99"]


def test_backtest_parameter_sweep_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    path = write_sweep_csv(tmp_path)
    output_dir = tmp_path / "sweep"

    assert cli.main(base_args(path, output_dir), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def write_sweep_csv(tmp_path):
    path = tmp_path / "prepared.csv"
    path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2025-01-01T00:00:00Z,100,101,99,100,1",
                "2025-01-01T01:00:00Z,94,95,93,94,1",
                "2025-01-01T02:00:00Z,106,107,105,106,1",
                "2025-01-01T03:00:00Z,111,112,110,111,1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def base_args(path, output_dir):
    return [
        "--symbol",
        "BTCUSDT",
        "--timeframe",
        "1h",
        "--csv",
        str(path),
        "--initial-balance",
        "10000",
        "--fee-rate",
        "0",
        "--strategy-type",
        "price_threshold",
        "--entry-below-values",
        "95,105",
        "--exit-above-values",
        "105,107",
        "--order-quantity",
        "1",
        "--output-dir",
        str(output_dir),
    ]


def replace_args(args: list[str], replacements: list[str]) -> list[str]:
    updated = list(args)
    for flag, value in zip(replacements[0::2], replacements[1::2]):
        index = updated.index(flag)
        updated[index + 1] = value
    return updated


def fake_comparison(runs: list[dict]) -> dict:
    recommendation = build_backtest_recommendation_summary(runs)
    return {
        "runs": runs,
        "recommendation": recommendation,
        "executive_summary": build_backtest_executive_summary(recommendation),
    }


def fake_run(
    run_name: str,
    *,
    score: str,
    total_return_pct: str,
    entry_below: str,
    exit_above: str,
    completed_round_trips: int = 10,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "run_name": run_name,
        "run_dir": run_name,
        "overall_score": score,
        "score_warnings": warnings or [],
        "summary": {
            "strategy_type": "price_threshold",
            "entry_below": entry_below,
            "exit_above": exit_above,
            "order_quantity": "1",
            "overall_score": score,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": "1",
            "max_drawdown_amount": "10",
            "profit_factor": "2",
            "win_rate_pct": "60",
            "completed_round_trips": completed_round_trips,
            "trades_count": completed_round_trips * 2,
        },
    }
