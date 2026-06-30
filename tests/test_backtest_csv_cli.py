import json
import csv
from decimal import Decimal
from io import StringIO

import pytest

from app.cli import run_backtest as cli
from app.engine.strategy_engine import StrategyEngine
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.csv_backtest import BacktestCsvError, load_candles_from_csv, run_csv_backtest


def write_csv(tmp_path, rows: list[str], header: str = "timestamp,open,high,low,close,volume"):
    path = tmp_path / "candles.csv"
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def run_price_threshold(path, **overrides):
    candles = load_candles_from_csv(path)
    return run_csv_backtest(
        candles=candles,
        symbol=overrides.get("symbol", "BTCUSDT"),
        timeframe=overrides.get("timeframe", "1h"),
        initial_balance=Decimal(overrides.get("initial_balance", "10000")),
        fee_rate=Decimal(overrides.get("fee_rate", "0.001")),
        strategy_type="price_threshold",
        parameters={
            "buy_below": Decimal(overrides.get("buy_below", "95")),
            "sell_above": Decimal(overrides.get("sell_above", "105")),
            "quantity": Decimal(overrides.get("quantity", "1")),
        },
    )


def run_moving_average_crossover(path, **overrides):
    candles = load_candles_from_csv(path)
    return run_csv_backtest(
        candles=candles,
        symbol=overrides.get("symbol", "BTCUSDT"),
        timeframe=overrides.get("timeframe", "1h"),
        initial_balance=Decimal(overrides.get("initial_balance", "10000")),
        fee_rate=Decimal(overrides.get("fee_rate", "0")),
        strategy_type="moving_average_crossover",
        parameters={
            "fast_window": int(overrides.get("fast_window", "2")),
            "slow_window": int(overrides.get("slow_window", "3")),
            "quantity": Decimal(overrides.get("quantity", "1")),
        },
    )


def test_csv_backtest_profitable_buy_sell_path_with_fees(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )

    result = run_price_threshold(path)

    assert result.result == "PASS"
    assert result.candles_count == 2
    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert result.trades[0].fee == Decimal("0.090")
    assert result.trades[1].fee == Decimal("0.110")
    assert result.final_balance == Decimal("10019.800")
    assert result.starting_balance == Decimal("10000")
    assert result.ending_balance == Decimal("10019.800")
    assert result.final_equity == Decimal("10019.800")
    assert result.total_return == Decimal("19.800")
    assert result.realized_pnl == Decimal("19.800")
    assert result.unrealized_pnl == Decimal("0")
    assert result.completed_round_trips == 1
    assert result.win_count == 1
    assert result.loss_count == 0
    assert result.fees_paid == Decimal("0.200")
    assert result.win_rate_pct == Decimal("100")
    assert result.breakeven_count == 0
    assert result.average_winning_trade_pnl == Decimal("19.800")
    assert result.average_losing_trade_pnl is None
    assert result.average_trade_pnl == Decimal("19.800")
    assert result.best_trade_pnl == Decimal("19.800")
    assert result.worst_trade_pnl == Decimal("19.800")
    assert result.profit_factor is None
    assert result.max_drawdown_amount == Decimal("0.090")
    assert result.exposure_pct == Decimal("50.0")


def test_csv_backtest_trade_diagnostics_for_win_loss_and_breakeven_round_trips(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,91,79,80,1",
            "2025-01-01T02:00:00Z,80,91,79,90,1",
            "2025-01-01T03:00:00Z,90,111,89,110,1",
            "2025-01-01T04:00:00Z,110,111,89,90,1",
            "2025-01-01T05:00:00Z,90,91,89,90,1",
        ],
    )

    result = run_price_threshold(path, fee_rate="0", sell_above="75")

    assert result.completed_round_trips == 3
    assert result.win_count == 1
    assert result.loss_count == 1
    assert result.breakeven_count == 1
    assert result.win_rate_pct == Decimal("33.33333333333333333333333333")
    assert result.average_winning_trade_pnl == Decimal("20")
    assert result.average_losing_trade_pnl == Decimal("-10")
    assert result.average_trade_pnl == Decimal("3.333333333333333333333333333")
    assert result.best_trade_pnl == Decimal("20")
    assert result.worst_trade_pnl == Decimal("-10")
    assert result.profit_factor == Decimal("2")
    assert result.max_drawdown_amount == Decimal("10")
    assert result.max_drawdown_pct == Decimal("0.100")
    assert result.exposure_pct == Decimal("50.0")


def test_csv_backtest_no_trade_path(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,99,100,1",
            "2025-01-01T01:00:00Z,101,102,100,101,1",
        ],
    )

    result = run_price_threshold(path)

    assert result.trades_count == 0
    assert result.buy_count == 0
    assert result.sell_count == 0
    assert result.final_balance == Decimal("10000")
    assert result.final_equity == Decimal("10000")
    assert result.win_rate_pct is None
    assert result.fees_paid == Decimal("0")
    assert result.breakeven_count == 0
    assert result.average_winning_trade_pnl is None
    assert result.average_losing_trade_pnl is None
    assert result.average_trade_pnl is None
    assert result.best_trade_pnl is None
    assert result.worst_trade_pnl is None
    assert result.profit_factor is None
    assert result.max_drawdown_amount == Decimal("0")
    assert result.exposure_pct == Decimal("0")


def test_csv_backtest_moving_average_crossover_buy_sell_path(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,10,10,10,10,1",
            "2025-01-01T02:00:00Z,9,9,9,9,1",
            "2025-01-01T03:00:00Z,12,12,12,12,1",
            "2025-01-01T04:00:00Z,5,5,5,5,1",
        ],
    )

    result = run_moving_average_crossover(path)

    assert result.result == "PASS"
    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert [trade.price for trade in result.trades] == [Decimal("12"), Decimal("5")]
    assert result.final_balance == Decimal("9993")
    assert result.realized_pnl == Decimal("-7")
    assert result.final_position_quantity == Decimal("0")


def test_csv_backtest_moving_average_crossover_no_trade_path(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,11,11,11,11,1",
            "2025-01-01T02:00:00Z,12,12,12,12,1",
            "2025-01-01T03:00:00Z,13,13,13,13,1",
        ],
    )

    result = run_moving_average_crossover(path)

    assert result.trades_count == 0
    assert result.final_balance == Decimal("10000")
    assert result.final_equity == Decimal("10000")


@pytest.mark.parametrize(
    ("parameters", "expected_error"),
    [
        ({"fast_window": 0, "slow_window": 3, "quantity": Decimal("1")}, "fast_window must be positive"),
        ({"fast_window": 3, "slow_window": 3, "quantity": Decimal("1")}, "fast_window must be smaller than slow_window"),
    ],
)
def test_csv_backtest_moving_average_crossover_invalid_windows(tmp_path, parameters, expected_error) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,10,10,10,10,1",
            "2025-01-01T02:00:00Z,9,9,9,9,1",
            "2025-01-01T03:00:00Z,12,12,12,12,1",
        ],
    )

    with pytest.raises(BacktestCsvError, match=expected_error):
        run_csv_backtest(
            candles=load_candles_from_csv(path),
            symbol="BTCUSDT",
            timeframe="1h",
            initial_balance=Decimal("10000"),
            fee_rate=Decimal("0"),
            strategy_type="moving_average_crossover",
            parameters=parameters,
        )


def test_csv_backtest_moving_average_crossover_requires_enough_candles(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,10,10,10,10,1",
            "2025-01-01T02:00:00Z,9,9,9,9,1",
        ],
    )

    with pytest.raises(BacktestCsvError, match="need at least 4, got 3"):
        run_moving_average_crossover(path)


def test_csv_backtest_max_drawdown_and_buy_and_hold_metrics(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,91,79,80,1",
            "2025-01-01T02:00:00Z,80,111,80,110,1",
        ],
    )

    result = run_price_threshold(path)

    assert result.max_drawdown_pct > Decimal("0")
    assert result.equity_curve[1].equity == Decimal("9989.910")
    assert result.buy_and_hold_return_pct == Decimal("22.22222222222222222222222222")


def test_csv_loader_sorts_candles_and_rejects_duplicate_timestamps(tmp_path) -> None:
    unsorted_path = write_csv(
        tmp_path,
        [
            "2025-01-01T01:00:00Z,100,101,99,100,1",
            "2025-01-01T00:00:00Z,90,91,89,90,1",
        ],
    )
    assert [candle.close for candle in load_candles_from_csv(unsorted_path)] == [Decimal("90"), Decimal("100")]

    duplicate_path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,99,100,1",
            "2025-01-01T00:00:00Z,101,102,100,101,1",
        ],
    )
    with pytest.raises(BacktestCsvError, match="duplicate candle timestamp"):
        load_candles_from_csv(duplicate_path)


def test_csv_loader_rejects_missing_columns_and_non_positive_prices(tmp_path) -> None:
    missing_column_path = write_csv(
        tmp_path,
        ["2025-01-01T00:00:00Z,100,101,99,1"],
        header="timestamp,open,high,low,volume",
    )
    with pytest.raises(BacktestCsvError, match="missing required columns: close"):
        load_candles_from_csv(missing_column_path)

    bad_price_path = write_csv(tmp_path, ["2025-01-01T00:00:00Z,100,101,99,0,1"])
    with pytest.raises(BacktestCsvError, match="close must be positive"):
        load_candles_from_csv(bad_price_path)


def test_csv_backtest_does_not_look_ahead(tmp_path, monkeypatch) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,91,89,90,1",
            "2025-01-01T02:00:00Z,90,111,89,110,1",
        ],
    )
    original_evaluate = StrategyEngine.evaluate
    seen_lengths: list[int] = []
    seen_last_closes: list[Decimal] = []

    def spy_evaluate(**kwargs):
        candles = kwargs["candles"]
        seen_lengths.append(len(candles))
        seen_last_closes.append(candles[-1].close)
        return original_evaluate(**kwargs)

    monkeypatch.setattr(StrategyEngine, "evaluate", spy_evaluate)

    result = run_price_threshold(path)

    assert result.candles_count == 3
    assert seen_lengths == [1, 2, 3]
    assert seen_last_closes == [Decimal("90"), Decimal("90"), Decimal("110")]


def test_run_backtest_cli_outputs_json_summary_and_details(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = cli.main(
        [
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--csv",
            str(path),
            "--initial-balance",
            "10000",
            "--fee-rate",
            "0.001",
            "--strategy-type",
            "price_threshold",
            "--entry-below",
            "95",
            "--exit-above",
            "105",
            "--order-quantity",
            "1",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    body = json.loads(stdout.getvalue())
    assert body["result"] == "PASS"
    assert body["symbol"] == "BTCUSDT"
    assert body["trades_count"] == 2
    assert [trade["side"] for trade in body["trades"]] == ["buy", "sell"]
    assert len(body["equity_curve"]) == 2


def test_run_backtest_output_dir_writes_summary_trades_and_equity_curve(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )
    output_dir = tmp_path / "runs" / "demo_001"

    exit_code = cli.main(base_cli_args(path) + ["--output-dir", str(output_dir)], stdout=StringIO())

    assert exit_code == 0
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["result"] == "PASS"
    assert summary["starting_balance"] == "10000"
    assert summary["ending_balance"] == "10019.8"
    assert summary["total_return"] == "19.8"
    assert summary["completed_round_trips"] == 1
    assert summary["win_count"] == 1
    assert summary["loss_count"] == 0
    assert summary["breakeven_count"] == 0
    assert summary["average_winning_trade_pnl"] == "19.8"
    assert summary["average_trade_pnl"] == "19.8"
    assert summary["best_trade_pnl"] == "19.8"
    assert summary["worst_trade_pnl"] == "19.8"
    assert summary["profit_factor"] is None
    assert summary["max_drawdown_amount"] == "0.09"
    assert summary["exposure_pct"] == "50"
    assert "trades" not in summary
    assert "equity_curve" not in summary
    with (output_dir / "trades.csv").open(newline="", encoding="utf-8") as handle:
        trades = list(csv.DictReader(handle))
    with (output_dir / "equity_curve.csv").open(newline="", encoding="utf-8") as handle:
        equity_curve = list(csv.DictReader(handle))
    assert [trade["side"] for trade in trades] == ["buy", "sell"]
    assert trades[0]["fee"] == "0.09"
    assert [point["close_price"] for point in equity_curve] == ["90", "110"]
    assert [point["drawdown_amount"] for point in equity_curve] == ["0.09", "0"]


def test_run_backtest_summary_only_prints_compact_stdout_and_still_writes_files(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )
    output_dir = tmp_path / "runs" / "demo_002"
    stdout = StringIO()

    exit_code = cli.main(
        base_cli_args(path) + ["--summary-only", "--output-dir", str(output_dir)],
        stdout=stdout,
    )

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed["result"] == "PASS"
    assert "trades" not in printed
    assert "equity_curve" not in printed
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "trades.csv").exists()
    assert (output_dir / "equity_curve.csv").exists()


def test_run_backtest_cli_supports_moving_average_crossover_and_summary_params(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,10,10,10,10,1",
            "2025-01-01T02:00:00Z,9,9,9,9,1",
            "2025-01-01T03:00:00Z,12,12,12,12,1",
            "2025-01-01T04:00:00Z,5,5,5,5,1",
        ],
    )
    output_dir = tmp_path / "runs" / "ma_001"
    stdout = StringIO()

    exit_code = cli.main(
        moving_average_cli_args(path)
        + ["--summary-only", "--output-dir", str(output_dir)],
        stdout=stdout,
    )

    assert exit_code == 0
    printed = json.loads(stdout.getvalue())
    assert printed["strategy_type"] == "moving_average_crossover"
    assert printed["fast_window"] == "2"
    assert printed["slow_window"] == "3"
    assert printed["trades_count"] == 2
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["strategy_type"] == "moving_average_crossover"
    assert summary["fast_window"] == "2"
    assert summary["slow_window"] == "3"


def test_run_backtest_output_dir_refuses_existing_files_without_overwrite(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )
    output_dir = tmp_path / "runs" / "demo_003"
    assert cli.main(base_cli_args(path) + ["--output-dir", str(output_dir)], stdout=StringIO()) == 0
    stdout = StringIO()

    exit_code = cli.main(base_cli_args(path) + ["--output-dir", str(output_dir)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": "output files already exist; pass --overwrite to replace: summary.json, trades.csv, equity_curve.csv",
        "result": "FAIL",
    }


def test_run_backtest_output_dir_overwrite_replaces_existing_files(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )
    output_dir = tmp_path / "runs" / "demo_004"
    output_dir.mkdir(parents=True)
    (output_dir / "summary.json").write_text("old\n", encoding="utf-8")
    (output_dir / "trades.csv").write_text("old\n", encoding="utf-8")
    (output_dir / "equity_curve.csv").write_text("old\n", encoding="utf-8")

    exit_code = cli.main(base_cli_args(path) + ["--output-dir", str(output_dir), "--overwrite"], stdout=StringIO())

    assert exit_code == 0
    assert json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))["result"] == "PASS"
    assert "old" not in (output_dir / "trades.csv").read_text(encoding="utf-8")
    assert "old" not in (output_dir / "equity_curve.csv").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("extra_args", "expected_error"),
    [
        (["--csv", "missing.csv"], "CSV file does not exist: missing.csv"),
        (["--initial-balance", "0"], "initial_balance must be positive"),
        (["--fee-rate", "-0.001"], "fee_rate must not be negative"),
        (["--order-quantity", "0"], "order-quantity must be positive"),
        (["--strategy-type", "moving_average_cross"], "unsupported strategy type: moving_average_cross"),
    ],
)
def test_run_backtest_cli_invalid_values_fail_cleanly(tmp_path, extra_args, expected_error) -> None:
    path = write_csv(tmp_path, ["2025-01-01T00:00:00Z,100,101,99,100,1"])
    args = replace_args(base_cli_args(path), extra_args)
    stdout = StringIO()

    exit_code = cli.main(args, stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {"error": expected_error, "result": "FAIL"}


def test_run_backtest_cli_rejects_output_dir_that_is_file(tmp_path) -> None:
    path = write_csv(tmp_path, ["2025-01-01T00:00:00Z,100,101,99,100,1"])
    output_path = tmp_path / "not_a_dir"
    output_path.write_text("", encoding="utf-8")
    stdout = StringIO()

    exit_code = cli.main(base_cli_args(path) + ["--output-dir", str(output_path)], stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output-dir points to a file: {output_path}",
        "result": "FAIL",
    }


def test_run_backtest_cli_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,100,101,89,90,1",
            "2025-01-01T01:00:00Z,90,111,90,110,1",
        ],
    )

    assert cli.main(base_cli_args(path), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def test_run_backtest_cli_moving_average_crossover_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    path = write_csv(
        tmp_path,
        [
            "2025-01-01T00:00:00Z,10,10,10,10,1",
            "2025-01-01T01:00:00Z,10,10,10,10,1",
            "2025-01-01T02:00:00Z,9,9,9,9,1",
            "2025-01-01T03:00:00Z,12,12,12,12,1",
            "2025-01-01T04:00:00Z,5,5,5,5,1",
        ],
    )

    assert cli.main(moving_average_cli_args(path), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []


def test_run_backtest_cli_returns_fail_for_invalid_csv(tmp_path) -> None:
    path = write_csv(tmp_path, ["not-a-date,100,101,99,100,1"])
    stdout = StringIO()

    exit_code = cli.main(
        [
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--csv",
            str(path),
            "--initial-balance",
            "10000",
            "--fee-rate",
            "0.001",
            "--strategy-type",
            "price_threshold",
            "--entry-below",
            "95",
            "--exit-above",
            "105",
            "--order-quantity",
            "1",
        ],
        stdout=stdout,
    )

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": "row 2: timestamp is not parseable",
        "result": "FAIL",
    }


def base_cli_args(path):
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
        "0.001",
        "--strategy-type",
        "price_threshold",
        "--entry-below",
        "95",
        "--exit-above",
        "105",
        "--order-quantity",
        "1",
    ]


def moving_average_cli_args(path):
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
        "moving_average_crossover",
        "--fast-window",
        "2",
        "--slow-window",
        "3",
        "--order-quantity",
        "1",
    ]


def replace_args(args: list[str], replacements: list[str]) -> list[str]:
    updated = list(args)
    for flag, value in zip(replacements[0::2], replacements[1::2]):
        index = updated.index(flag)
        updated[index + 1] = value
    return updated
