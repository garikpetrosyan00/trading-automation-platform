import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class BacktestArtifactCatalogError(ValueError):
    pass


ARTIFACT_TYPES = {"run", "comparison_report", "sweep", "json_report", "markdown_report", "validation_output"}


def build_backtest_artifact_catalog(
    artifact_root: str | Path,
    *,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    if artifact_type is not None and artifact_type not in ARTIFACT_TYPES:
        raise BacktestArtifactCatalogError(f"unsupported artifact type filter: {artifact_type}")

    root = Path(artifact_root)
    if not root.exists():
        raise BacktestArtifactCatalogError(f"artifact root does not exist: {root}")
    if not root.is_dir():
        raise BacktestArtifactCatalogError(f"artifact root is not a directory: {root}")

    artifacts: list[dict[str, Any]] = []
    warnings: list[str] = []
    discovered_paths: set[Path] = set()

    for child in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name):
        if not _safe_part(child.name):
            warnings.append(f"ignored unsafe artifact directory: {child.name}")
            continue
        if (child / "sweep_summary.json").is_file():
            artifacts.append(_sweep_artifact(root, child, warnings=warnings))
            discovered_paths.add(child / "sweep_summary.json")
            continue
        summary_path = _first_existing(child, ("summary.json", "run/summary.json"))
        if summary_path is not None:
            artifacts.append(_run_artifact(root, child, summary_path, warnings=warnings))
            discovered_paths.add(summary_path)

    for json_path in sorted(root.rglob("*.json"), key=lambda item: _relative_path(root, item)):
        if json_path in discovered_paths or _is_summary_or_manifest_json(root, json_path):
            continue
        artifact = _json_artifact(root, json_path, warnings=warnings)
        if artifact is not None:
            artifacts.append(artifact)

    for markdown_path in sorted(root.rglob("*.md"), key=lambda item: _relative_path(root, item)):
        if _is_hidden_or_unsafe(root, markdown_path):
            continue
        artifacts.append(_markdown_artifact(root, markdown_path))

    artifacts = [item for item in artifacts if artifact_type is None or item["artifact_type"] == artifact_type]
    artifacts.sort(key=lambda item: (item["artifact_type"], item["label"], item["relative_path"]))

    return {
        "schema_version": "1",
        "artifact_root": _safe_root_label(root),
        "artifact_count": len(artifacts),
        "run_count": sum(1 for item in artifacts if item["artifact_type"] == "run"),
        "comparison_report_count": sum(1 for item in artifacts if item["artifact_type"] == "comparison_report"),
        "sweep_count": sum(1 for item in artifacts if item["artifact_type"] == "sweep"),
        "markdown_report_count": sum(1 for item in artifacts if item["artifact_type"] == "markdown_report"),
        "json_report_count": sum(1 for item in artifacts if item["artifact_type"] in {"comparison_report", "json_report", "validation_output"}),
        "artifacts": artifacts,
        "catalog_warnings": sorted(set(warnings)),
    }


def compact_backtest_artifact_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": catalog["schema_version"],
        "artifact_root": catalog["artifact_root"],
        "artifact_count": catalog["artifact_count"],
        "run_count": catalog["run_count"],
        "comparison_report_count": catalog["comparison_report_count"],
        "sweep_count": catalog["sweep_count"],
        "markdown_report_count": catalog["markdown_report_count"],
        "json_report_count": catalog["json_report_count"],
        "artifacts": [
            {
                "artifact_type": item["artifact_type"],
                "label": item["label"],
                "relative_path": item["relative_path"],
            }
            for item in catalog.get("artifacts", [])
        ],
        "catalog_warnings": catalog["catalog_warnings"],
    }


def _run_artifact(root: Path, directory: Path, summary_path: Path, *, warnings: list[str]) -> dict[str, Any]:
    summary = _read_json(summary_path, warnings=warnings, root=root)
    return _artifact_entry(
        artifact_type="run",
        label=directory.name,
        relative_path=_relative_path(root, directory),
        strategy=summary.get("strategy_type"),
        symbol=summary.get("symbol"),
        timeframe=summary.get("timeframe"),
        overall_score=summary.get("overall_score"),
        has_manifest=_has_any(directory, ("manifest.json", "bundle/manifest.json")),
        has_summary=True,
    )


def _sweep_artifact(root: Path, directory: Path, *, warnings: list[str]) -> dict[str, Any]:
    summary = _read_json(directory / "sweep_summary.json", warnings=warnings, root=root)
    sweep_summary = summary.get("sweep_summary") if isinstance(summary.get("sweep_summary"), dict) else {}
    return _artifact_entry(
        artifact_type="sweep",
        label=directory.name,
        relative_path=_relative_path(root, directory),
        strategy=summary.get("strategy_type"),
        symbol=summary.get("symbol"),
        timeframe=summary.get("timeframe"),
        overall_score=sweep_summary.get("best_overall_score"),
        recommendation_status=sweep_summary.get("recommendation_status"),
        acceptance_status=sweep_summary.get("acceptance_status"),
        executive_decision=sweep_summary.get("executive_decision"),
        validation_status=sweep_summary.get("validation_status"),
        has_manifest=False,
        has_summary=True,
    )


def _json_artifact(root: Path, path: Path, *, warnings: list[str]) -> dict[str, Any] | None:
    if _is_hidden_or_unsafe(root, path):
        return None
    payload = _read_json(path, warnings=warnings, root=root)
    if not payload:
        return None
    artifact_type = _json_artifact_type(payload)
    recommendation = payload.get("recommendation") if isinstance(payload.get("recommendation"), dict) else {}
    executive_summary = payload.get("executive_summary") if isinstance(payload.get("executive_summary"), dict) else {}
    manifest = payload.get("export_manifest") if isinstance(payload.get("export_manifest"), dict) else {}
    return _artifact_entry(
        artifact_type=artifact_type,
        label=path.stem,
        relative_path=_relative_path(root, path),
        strategy=_first_run_summary_value(payload, "strategy_type"),
        symbol=_first_run_summary_value(payload, "symbol"),
        timeframe=_first_run_summary_value(payload, "timeframe"),
        overall_score=executive_summary.get("overall_score") or _first_run_value(payload, "overall_score"),
        recommendation_status=recommendation.get("recommendation_status") or executive_summary.get("recommendation_status"),
        acceptance_status=recommendation.get("acceptance_status") or executive_summary.get("acceptance_status"),
        executive_decision=executive_summary.get("decision"),
        validation_status=payload.get("validation_status") or manifest.get("validation_status"),
        has_manifest=bool(manifest),
        has_summary=False,
    )


def _markdown_artifact(root: Path, path: Path) -> dict[str, Any]:
    return _artifact_entry(
        artifact_type="markdown_report",
        label=path.stem,
        relative_path=_relative_path(root, path),
        has_manifest=False,
        has_summary=False,
    )


def _artifact_entry(
    *,
    artifact_type: str,
    label: str,
    relative_path: str,
    strategy: Any = None,
    symbol: Any = None,
    timeframe: Any = None,
    overall_score: Any = None,
    recommendation_status: Any = None,
    acceptance_status: Any = None,
    executive_decision: Any = None,
    validation_status: Any = None,
    has_manifest: bool,
    has_summary: bool,
) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "label": str(label),
        "relative_path": relative_path,
        "strategy": _safe_scalar(strategy),
        "symbol": _safe_scalar(symbol),
        "timeframe": _safe_scalar(timeframe),
        "overall_score": _safe_numeric_or_scalar(overall_score),
        "recommendation_status": _safe_scalar(recommendation_status),
        "acceptance_status": _safe_scalar(acceptance_status),
        "executive_decision": _safe_scalar(executive_decision),
        "validation_status": _safe_scalar(validation_status),
        "has_manifest": has_manifest,
        "has_summary": has_summary,
    }


def _json_artifact_type(payload: dict[str, Any]) -> str:
    export_manifest = payload.get("export_manifest") if isinstance(payload.get("export_manifest"), dict) else {}
    if export_manifest.get("artifact_type") == "backtest_comparison_report" or (
        isinstance(payload.get("runs"), list) and isinstance(payload.get("rankings"), dict)
    ):
        return "comparison_report"
    if payload.get("validation_status") in {"passed", "passed_with_warnings", "failed"}:
        return "validation_output"
    return "json_report"


def _read_json(path: Path, *, warnings: list[str], root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warnings.append(f"malformed_json:{_relative_path(root, path)}")
        return {}
    if not isinstance(payload, dict):
        warnings.append(f"json_not_object:{_relative_path(root, path)}")
        return {}
    if _contains_non_finite_number(payload):
        warnings.append(f"json_contains_non_finite:{_relative_path(root, path)}")
        return {}
    return payload


def _first_existing(directory: Path, relative_paths: tuple[str, ...]) -> Path | None:
    for relative_path in relative_paths:
        path = directory / relative_path
        if path.is_file():
            return path
    return None


def _has_any(directory: Path, relative_paths: tuple[str, ...]) -> bool:
    return _first_existing(directory, relative_paths) is not None


def _first_run_summary_value(payload: dict[str, Any], field: str) -> Any:
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            summary = run.get("summary") if isinstance(run, dict) and isinstance(run.get("summary"), dict) else {}
            if summary.get(field) is not None:
                return summary.get(field)
    return None


def _first_run_value(payload: dict[str, Any], field: str) -> Any:
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            if isinstance(run, dict) and run.get(field) is not None:
                return run.get(field)
    return None


def _is_summary_or_manifest_json(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return relative.name in {"summary.json", "sweep_summary.json", "manifest.json"}


def _is_hidden_or_unsafe(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(not _safe_part(part) for part in relative.parts)


def _safe_part(part: str) -> bool:
    return bool(part) and part not in {".", ".."} and "\x00" not in part and "/" not in part and "\\" not in part and ".." not in part


def _safe_root_label(root: Path) -> str:
    return root.as_posix() if not root.is_absolute() else root.name


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _safe_scalar(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (str, int, Decimal)):
        return str(value)
    if isinstance(value, float):
        return str(value) if Decimal(str(value)).is_finite() else None
    return None


def _safe_numeric_or_scalar(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return _safe_scalar(value)
    return str(value) if parsed.is_finite() else None


def _contains_non_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return True
        return not parsed.is_finite()
    if isinstance(value, str) and value in {"NaN", "Infinity", "-Infinity"}:
        return True
    if isinstance(value, list):
        return any(_contains_non_finite_number(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_non_finite_number(item) for item in value.values())
    return False
