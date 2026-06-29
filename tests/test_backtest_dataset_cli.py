import csv
import json
from io import StringIO

from app.cli import prepare_backtest_dataset as cli
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


def write_raw_csv(tmp_path, name: str, rows: list[str], header: str = "timestamp,open,high,low,close,volume"):
    path = tmp_path / name
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def read_csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def base_args(input_path, output_path):
    return [
        "--symbol",
        "BTCUSDT",
        "--timeframe",
        "1h",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]


def test_prepare_backtest_dataset_one_valid_csv(tmp_path) -> None:
    raw = write_raw_csv(tmp_path, "raw.csv", ["2025-01-01T00:00:00Z,95000,96000,94000,95500,123.45"])
    output = tmp_path / "datasets" / "prepared.csv"
    stdout = StringIO()

    exit_code = cli.main(base_args(raw, output), stdout=stdout)

    assert exit_code == 0
    assert read_csv_rows(output) == [
        {
            "timestamp": "2025-01-01T00:00:00Z",
            "open": "95000",
            "high": "96000",
            "low": "94000",
            "close": "95500",
            "volume": "123.45",
        }
    ]
    summary = json.loads(stdout.getvalue())
    assert summary["rows_in"] == 1
    assert summary["rows_out"] == 1
    assert summary["missing_intervals_count"] == 0
    assert summary["output_path"] == str(output)


def test_prepare_backtest_dataset_multiple_csvs_merged_and_sorted(tmp_path) -> None:
    raw_a = write_raw_csv(tmp_path, "raw_a.csv", ["2025-01-01T02:00:00Z,3,4,2,3,1"])
    raw_b = write_raw_csv(tmp_path, "raw_b.csv", ["2025-01-01T00:00:00Z,1,2,1,1,1"])
    output = tmp_path / "prepared.csv"

    exit_code = cli.main(
        base_args(raw_a, output) + ["--input", str(raw_b)],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert [row["timestamp"] for row in read_csv_rows(output)] == [
        "2025-01-01T00:00:00Z",
        "2025-01-01T02:00:00Z",
    ]


def test_prepare_backtest_dataset_date_filtering_is_start_inclusive_end_exclusive(tmp_path) -> None:
    raw = write_raw_csv(
        tmp_path,
        "raw.csv",
        [
            "2024-12-31T23:00:00Z,1,2,1,1,1",
            "2025-01-01T00:00:00Z,2,3,1,2,1",
            "2025-01-02T00:00:00Z,3,4,2,3,1",
        ],
    )
    output = tmp_path / "prepared.csv"

    exit_code = cli.main(
        base_args(raw, output) + ["--start", "2025-01-01", "--end", "2025-01-02"],
        stdout=StringIO(),
    )

    assert exit_code == 0
    assert [row["timestamp"] for row in read_csv_rows(output)] == ["2025-01-01T00:00:00Z"]


def test_prepare_backtest_dataset_duplicate_rejection_and_dedupe_modes(tmp_path) -> None:
    raw = write_raw_csv(
        tmp_path,
        "raw.csv",
        [
            "2025-01-01T00:00:00Z,1,2,1,1,1",
            "2025-01-01T00:00:00Z,9,10,8,9,1",
        ],
    )
    output = tmp_path / "prepared.csv"
    stdout = StringIO()

    assert cli.main(base_args(raw, output), stdout=stdout) == 1
    assert json.loads(stdout.getvalue()) == {
        "error": "duplicate timestamp found: 2025-01-01T00:00:00Z",
        "result": "FAIL",
    }

    keep_first_output = tmp_path / "keep_first.csv"
    assert cli.main(base_args(raw, keep_first_output) + ["--dedupe", "keep-first"], stdout=StringIO()) == 0
    assert read_csv_rows(keep_first_output)[0]["open"] == "1"

    keep_last_output = tmp_path / "keep_last.csv"
    assert cli.main(base_args(raw, keep_last_output) + ["--dedupe", "keep-last"], stdout=StringIO()) == 0
    assert read_csv_rows(keep_last_output)[0]["open"] == "9"


def test_prepare_backtest_dataset_invalid_ohlc_values(tmp_path) -> None:
    raw = write_raw_csv(tmp_path, "raw.csv", ["2025-01-01T00:00:00Z,5,4,1,5,1"])
    stdout = StringIO()

    exit_code = cli.main(base_args(raw, tmp_path / "prepared.csv"), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"{raw}: row 2: high must be greater than or equal to open and close",
        "result": "FAIL",
    }


def test_prepare_backtest_dataset_missing_required_columns(tmp_path) -> None:
    raw = write_raw_csv(
        tmp_path,
        "raw.csv",
        ["2025-01-01T00:00:00Z,1,2,1,1"],
        header="timestamp,open,high,low,volume",
    )
    stdout = StringIO()

    exit_code = cli.main(base_args(raw, tmp_path / "prepared.csv"), stdout=stdout)

    assert exit_code == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"{raw}: missing required column: close",
        "result": "FAIL",
    }


def test_prepare_backtest_dataset_overwrite_refusal_and_success(tmp_path) -> None:
    raw = write_raw_csv(tmp_path, "raw.csv", ["2025-01-01T00:00:00Z,1,2,1,1,1"])
    output = tmp_path / "prepared.csv"
    output.write_text("old\n", encoding="utf-8")
    stdout = StringIO()

    assert cli.main(base_args(raw, output), stdout=stdout) == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output file already exists; pass --overwrite to replace: {output}",
        "result": "FAIL",
    }
    assert cli.main(base_args(raw, output) + ["--overwrite"], stdout=StringIO()) == 0
    assert "old" not in output.read_text(encoding="utf-8")


def test_prepare_backtest_dataset_summary_json_and_gap_detection_for_1h(tmp_path) -> None:
    raw = write_raw_csv(
        tmp_path,
        "raw.csv",
        [
            "2025-01-01T00:00:00Z,1,2,1,1,1",
            "2025-01-01T03:00:00Z,2,3,2,2,1",
        ],
    )
    output = tmp_path / "prepared.csv"
    summary_json = tmp_path / "prepared.summary.json"

    assert cli.main(base_args(raw, output) + ["--summary-json", str(summary_json)], stdout=StringIO()) == 0

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["missing_intervals_count"] == 2
    assert summary["largest_gap"] == "3h"


def test_prepare_backtest_dataset_accepts_timestamp_aliases(tmp_path) -> None:
    raw = write_raw_csv(
        tmp_path,
        "raw.csv",
        ["2025-01-01T00:00:00Z,1,2,1,1,1"],
        header="open_time,open,high,low,close,volume",
    )
    output = tmp_path / "prepared.csv"

    assert cli.main(base_args(raw, output), stdout=StringIO()) == 0

    assert read_csv_rows(output)[0]["timestamp"] == "2025-01-01T00:00:00Z"


def test_prepare_backtest_dataset_output_directory_fails_cleanly(tmp_path) -> None:
    raw = write_raw_csv(tmp_path, "raw.csv", ["2025-01-01T00:00:00Z,1,2,1,1,1"])
    stdout = StringIO()

    assert cli.main(base_args(raw, tmp_path), stdout=stdout) == 1
    assert json.loads(stdout.getvalue()) == {
        "error": f"output path points to a directory: {tmp_path}",
        "result": "FAIL",
    }


def test_prepare_backtest_dataset_does_not_touch_runtime_audit_tables(db_session, tmp_path) -> None:
    raw = write_raw_csv(tmp_path, "raw.csv", ["2025-01-01T00:00:00Z,1,2,1,1,1"])

    assert cli.main(base_args(raw, tmp_path / "prepared.csv"), stdout=StringIO()) == 0

    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert ExecutionAttemptRepository(db_session).list_filtered(limit=10) == []
    assert ExecutionReconciliationJobRepository(db_session).list_filtered(limit=10) == []
    assert RunEventRepository(db_session).list_for_bot(bot_id=1) == []
