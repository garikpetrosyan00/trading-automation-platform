import json
import csv
from pathlib import Path
from typing import Any

from app.core.errors import AppError


RUNS_ROOT = Path("data/backtests/runs")

SUMMARY_FIELDS = (
    "result",
    "symbol",
    "timeframe",
    "candles_count",
    "initial_balance",
    "final_balance",
    "final_position_quantity",
    "final_equity",
    "total_return_pct",
    "realized_pnl",
    "unrealized_pnl",
    "trades_count",
    "buy_count",
    "sell_count",
    "win_rate_pct",
    "fees_paid",
    "max_drawdown_pct",
    "buy_and_hold_return_pct",
    "started_at",
    "ended_at",
    "strategy_type",
    "fee_rate",
    "entry_below",
    "exit_above",
    "order_quantity",
)


class LocalBacktestArtifactService:
    def __init__(self, runs_root: str | Path = RUNS_ROOT):
        self.runs_root = Path(runs_root)

    def read_run_summary(self, run_name: str) -> dict[str, Any]:
        run_dir = self._safe_child_dir(run_name)
        payload = self._read_json(self._first_existing(run_dir, ("summary.json", "run/summary.json")), "summary")
        return {
            "run_name": run_name,
            "artifact": "summary",
            "summary": {field: payload.get(field) for field in SUMMARY_FIELDS if field in payload},
        }

    def list_runs(self) -> dict[str, Any]:
        items = []
        for child in self._iter_safe_child_dirs():
            summary_path = self._optional_first_existing(child, ("summary.json", "run/summary.json"))
            if summary_path is None:
                continue
            summary = self._safe_read_json(summary_path)
            items.append(self._catalog_item(child.name, child, summary=summary))
        return {"items": sorted(items, key=lambda item: item["name"])}

    def read_run_report_markdown(self, run_name: str) -> str:
        run_dir = self._safe_child_dir(run_name)
        report_path = self._first_existing(run_dir, ("report.md", "bundle/report.md"))
        try:
            content = report_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AppError("Local backtest report is not readable", status_code=404, error_code="artifact_not_found") from exc
        return self._sanitize_markdown(content)

    def read_bundle_manifest(self, bundle_name: str) -> dict[str, Any]:
        bundle_dir = self._safe_child_dir(bundle_name)
        payload = self._read_json(
            self._first_existing(bundle_dir, ("manifest.json", "bundle/manifest.json")),
            "manifest",
        )
        return {
            "bundle_name": bundle_name,
            "artifact": "manifest",
            "manifest": {
                "title": payload.get("title"),
                "comparison_included": bool(payload.get("comparison_included")),
                "report_included": bool(payload.get("report_included")),
                "files": self._manifest_files(payload.get("files")),
                "unavailable": self._manifest_unavailable(payload.get("unavailable")),
            },
        }

    def list_bundles(self) -> dict[str, Any]:
        items = []
        for child in self._iter_safe_child_dirs():
            manifest_path = self._optional_first_existing(child, ("manifest.json", "bundle/manifest.json"))
            if manifest_path is None:
                continue
            manifest = self._safe_read_json(manifest_path)
            summary_path = self._optional_first_existing(child, ("summary.json", "bundle/summary.json", "run/summary.json"))
            summary = self._safe_read_json(summary_path) if summary_path is not None else {}
            item = self._catalog_item(child.name, child, summary=summary)
            item["title"] = manifest.get("title")
            item["comparison_included"] = bool(manifest.get("comparison_included"))
            item["report_included"] = bool(manifest.get("report_included"))
            items.append(item)
        return {"items": sorted(items, key=lambda item: item["name"])}

    def _safe_child_dir(self, name: str) -> Path:
        if not self._is_safe_name(name):
            raise AppError("Invalid local backtest artifact name", status_code=422, error_code="invalid_artifact_name")
        root = self.runs_root.resolve()
        candidate = (root / name).resolve()
        if root != candidate and root not in candidate.parents:
            raise AppError("Invalid local backtest artifact name", status_code=422, error_code="invalid_artifact_name")
        return candidate

    def _is_safe_name(self, name: str) -> bool:
        return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name and ".." not in name

    def _iter_safe_child_dirs(self) -> list[Path]:
        if not self.runs_root.is_dir():
            return []
        return [
            child
            for child in self.runs_root.iterdir()
            if child.is_dir() and self._is_safe_name(child.name)
        ]

    def _first_existing(self, base_dir: Path, relative_paths: tuple[str, ...]) -> Path:
        for relative_path in relative_paths:
            path = base_dir / relative_path
            if path.is_file():
                return path
        raise AppError("Local backtest artifact not found", status_code=404, error_code="artifact_not_found")

    def _optional_first_existing(self, base_dir: Path, relative_paths: tuple[str, ...]) -> Path | None:
        for relative_path in relative_paths:
            path = base_dir / relative_path
            if path.is_file():
                return path
        return None

    def _read_json(self, path: Path, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AppError(f"Local backtest {label} is not readable", status_code=404, error_code="artifact_not_found") from exc
        if not isinstance(payload, dict):
            raise AppError(f"Local backtest {label} is not a JSON object", status_code=404, error_code="artifact_not_found")
        return payload

    def _safe_read_json(self, path: Path | None) -> dict[str, Any]:
        if path is None:
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _catalog_item(self, name: str, directory: Path, *, summary: dict[str, Any]) -> dict[str, Any]:
        trades_path = self._optional_first_existing(directory, ("trades.csv", "run/trades.csv", "bundle/trades.csv"))
        equity_curve_path = self._optional_first_existing(
            directory,
            ("equity_curve.csv", "run/equity_curve.csv", "bundle/equity_curve.csv"),
        )
        return {
            "name": name,
            "symbol": summary.get("symbol"),
            "timeframe": summary.get("timeframe"),
            "artifacts": {
                "summary_json": self._optional_first_existing(directory, ("summary.json", "run/summary.json")) is not None,
                "report_md": self._optional_first_existing(directory, ("report.md", "bundle/report.md")) is not None,
                "trades_csv": trades_path is not None,
                "equity_curve_csv": equity_curve_path is not None,
                "manifest_json": self._optional_first_existing(directory, ("manifest.json", "bundle/manifest.json")) is not None,
            },
            "row_counts": {
                "trades": self._count_csv_rows(trades_path),
                "equity_curve": self._count_csv_rows(equity_curve_path),
            },
        }

    def _manifest_files(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        files = []
        for item in value:
            if isinstance(item, dict):
                files.append(
                    {
                        "name": item.get("name"),
                        "sha256": item.get("sha256"),
                        "rows": item.get("rows"),
                        "size_bytes": item.get("size_bytes"),
                    }
                )
        return files

    def _manifest_unavailable(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        unavailable = []
        for item in value:
            if isinstance(item, dict):
                unavailable.append({"file": item.get("file"), "reason": item.get("reason")})
        return unavailable

    def _count_csv_rows(self, path: Path | None) -> int | None:
        if path is None:
            return None
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                return sum(1 for _row in csv.DictReader(handle))
        except OSError:
            return None

    def _sanitize_markdown(self, content: str) -> str:
        replacements = {
            str(Path.cwd().resolve()): ".",
            str(self.runs_root.resolve()): str(RUNS_ROOT),
        }
        sanitized = content
        for raw, replacement in replacements.items():
            sanitized = sanitized.replace(raw, replacement)
        return sanitized
