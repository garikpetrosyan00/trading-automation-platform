import json
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

    def _safe_child_dir(self, name: str) -> Path:
        if not name or name in {".", ".."}:
            raise AppError("Invalid local backtest artifact name", status_code=422, error_code="invalid_artifact_name")
        if any(separator in name for separator in ("/", "\\")) or ".." in name:
            raise AppError("Invalid local backtest artifact name", status_code=422, error_code="invalid_artifact_name")
        root = self.runs_root.resolve()
        candidate = (root / name).resolve()
        if root != candidate and root not in candidate.parents:
            raise AppError("Invalid local backtest artifact name", status_code=422, error_code="invalid_artifact_name")
        return candidate

    def _first_existing(self, base_dir: Path, relative_paths: tuple[str, ...]) -> Path:
        for relative_path in relative_paths:
            path = base_dir / relative_path
            if path.is_file():
                return path
        raise AppError("Local backtest artifact not found", status_code=404, error_code="artifact_not_found")

    def _read_json(self, path: Path, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AppError(f"Local backtest {label} is not readable", status_code=404, error_code="artifact_not_found") from exc
        if not isinstance(payload, dict):
            raise AppError(f"Local backtest {label} is not a JSON object", status_code=404, error_code="artifact_not_found")
        return payload

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

    def _sanitize_markdown(self, content: str) -> str:
        replacements = {
            str(Path.cwd().resolve()): ".",
            str(self.runs_root.resolve()): str(RUNS_ROOT),
        }
        sanitized = content
        for raw, replacement in replacements.items():
            sanitized = sanitized.replace(raw, replacement)
        return sanitized
