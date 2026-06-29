import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


class BacktestDemoBundleError(ValueError):
    pass


def export_backtest_demo_bundle(
    *,
    run_dir: str | Path,
    output_dir: str | Path,
    comparison_json: str | Path | None = None,
    report_md: str | Path | None = None,
    title: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    source_run_dir = Path(run_dir)
    destination = Path(output_dir)
    _validate_run_dir(source_run_dir)
    _prepare_output_dir(destination, overwrite=overwrite)

    manifest: dict[str, Any] = {
        "title": title or "Backtest Demo Bundle",
        "source_run_dir": str(source_run_dir),
        "comparison_included": False,
        "report_included": False,
        "files": [],
        "unavailable": [],
    }

    _copy_required(source_run_dir / "summary.json", destination / "summary.json", manifest)
    _copy_optional(source_run_dir / "trades.csv", destination / "trades.csv", manifest, label="trades.csv")
    _copy_optional(
        source_run_dir / "equity_curve.csv",
        destination / "equity_curve.csv",
        manifest,
        label="equity_curve.csv",
    )
    if comparison_json is not None:
        included = _copy_optional(
            Path(comparison_json),
            destination / "comparison.json",
            manifest,
            label="comparison.json",
        )
        manifest["comparison_included"] = included
    if report_md is not None:
        included = _copy_optional(Path(report_md), destination / "report.md", manifest, label="report.md")
        manifest["report_included"] = included

    readme = _bundle_readme(manifest)
    (destination / "README.md").write_text(readme, encoding="utf-8")
    _append_file_manifest(destination / "README.md", manifest)
    _append_manifest_placeholder(manifest)
    (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _validate_run_dir(run_dir: Path) -> None:
    if not run_dir.exists():
        raise BacktestDemoBundleError(f"run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise BacktestDemoBundleError(f"run path is not a directory: {run_dir}")
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise BacktestDemoBundleError(f"summary.json does not exist: {summary_path}")
    if not summary_path.is_file():
        raise BacktestDemoBundleError(f"summary.json path is not a file: {summary_path}")


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise BacktestDemoBundleError(f"output-dir points to a file: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise BacktestDemoBundleError(f"output directory is not empty; pass --overwrite to replace: {output_dir}")
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


def _copy_required(source: Path, destination: Path, manifest: dict[str, Any]) -> None:
    shutil.copyfile(source, destination)
    _append_file_manifest(destination, manifest)


def _copy_optional(source: Path, destination: Path, manifest: dict[str, Any], *, label: str) -> bool:
    if not source.is_file():
        manifest["unavailable"].append({"file": label, "source": str(source), "reason": "not available"})
        return False
    shutil.copyfile(source, destination)
    _append_file_manifest(destination, manifest)
    return True


def _append_file_manifest(path: Path, manifest: dict[str, Any]) -> None:
    relative_name = path.name
    manifest["files"] = [file for file in manifest["files"] if file["name"] != relative_name]
    manifest["files"].append(
        {
            "name": relative_name,
            "sha256": _sha256(path),
            "rows": _csv_row_count(path) if path.suffix == ".csv" else None,
            "size_bytes": path.stat().st_size,
        }
    )
    manifest["files"].sort(key=lambda file: file["name"])


def _append_manifest_placeholder(manifest: dict[str, Any]) -> None:
    manifest["files"] = [file for file in manifest["files"] if file["name"] != "manifest.json"]
    manifest["files"].append(
        {
            "name": "manifest.json",
            "sha256": None,
            "rows": None,
            "size_bytes": None,
        }
    )
    manifest["files"].sort(key=lambda file: file["name"])


def _csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_readme(manifest: dict[str, Any]) -> str:
    files = "\n".join(f"- `{file['name']}`" for file in manifest["files"]) or "- Unavailable"
    unavailable = "\n".join(
        f"- `{entry['file']}`: {entry['reason']}" for entry in manifest["unavailable"]
    ) or "- None"
    return (
        f"# {manifest['title']}\n"
        "\n"
        "This bundle contains local CSV backtest review artifacts only. It is not live or testnet execution and does not place orders.\n"
        "\n"
        f"Source run directory: `{manifest['source_run_dir']}`\n"
        "\n"
        "## Files\n"
        "\n"
        f"{files}\n"
        "\n"
        "## Unavailable Optional Files\n"
        "\n"
        f"{unavailable}\n"
    )
