import json
from decimal import Decimal
from io import StringIO

import pytest

from app.cli import run_backtest as cli
from app.engine.strategy_engine import StrategyEngine
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
    assert result.final_equity == Decimal("10019.800")
    assert result.realized_pnl == Decimal("19.800")
    assert result.unrealized_pnl == Decimal("0")
    assert result.fees_paid == Decimal("0.200")
    assert result.win_rate_pct == Decimal("100")


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
