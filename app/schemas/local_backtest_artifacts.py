from typing import Any

from pydantic import BaseModel


class LocalBacktestSummaryRead(BaseModel):
    run_name: str
    artifact: str
    summary: dict[str, Any]


class LocalBacktestArtifactAvailabilityRead(BaseModel):
    summary_json: bool
    report_md: bool
    trades_csv: bool
    equity_curve_csv: bool
    manifest_json: bool


class LocalBacktestArtifactRowCountsRead(BaseModel):
    trades: int | None = None
    equity_curve: int | None = None


class LocalBacktestCatalogItemRead(BaseModel):
    name: str
    symbol: str | None = None
    timeframe: str | None = None
    artifacts: LocalBacktestArtifactAvailabilityRead
    row_counts: LocalBacktestArtifactRowCountsRead


class LocalBacktestRunCatalogRead(BaseModel):
    items: list[LocalBacktestCatalogItemRead]


class LocalBacktestCompareRunRef(BaseModel):
    name: str | None = None
    path: str | None = None


class LocalBacktestCompareRequest(BaseModel):
    runs: list[LocalBacktestCompareRunRef]


class LocalBacktestComparisonRead(BaseModel):
    result: str
    runs_count: int
    ranking_metrics: list[str]
    runs: list[dict[str, Any]]
    rankings: dict[str, list[dict[str, Any]]]


class LocalBacktestManifestFileRead(BaseModel):
    name: str | None = None
    sha256: str | None = None
    rows: int | None = None
    size_bytes: int | None = None


class LocalBacktestManifestUnavailableRead(BaseModel):
    file: str | None = None
    reason: str | None = None


class LocalBacktestManifestRead(BaseModel):
    title: str | None = None
    comparison_included: bool
    report_included: bool
    files: list[LocalBacktestManifestFileRead]
    unavailable: list[LocalBacktestManifestUnavailableRead]


class LocalBacktestBundleManifestRead(BaseModel):
    bundle_name: str
    artifact: str
    manifest: LocalBacktestManifestRead


class LocalBacktestBundleCatalogItemRead(LocalBacktestCatalogItemRead):
    title: str | None = None
    comparison_included: bool
    report_included: bool


class LocalBacktestBundleCatalogRead(BaseModel):
    items: list[LocalBacktestBundleCatalogItemRead]


class LocalBacktestSweepArtifactsRead(BaseModel):
    sweep_summary_json: bool
    sweep_results_csv: bool
    sweep_report_md: bool


class LocalBacktestSweepResultRead(BaseModel):
    rank: int | None = None
    run_name: str | None = None
    entry_below: str | None = None
    exit_above: str | None = None
    final_equity: str | None = None
    total_return_pct: str | None = None
    trades_count: int | None = None
    win_rate_pct: str | None = None
    max_drawdown_pct: str | None = None
    fees_paid: str | None = None


class LocalBacktestSweepCatalogItemRead(BaseModel):
    name: str
    symbol: str | None = None
    timeframe: str | None = None
    combinations_count: int | None = None
    best_result: LocalBacktestSweepResultRead | None = None
    artifacts: LocalBacktestSweepArtifactsRead


class LocalBacktestSweepCatalogRead(BaseModel):
    items: list[LocalBacktestSweepCatalogItemRead]


class LocalBacktestSweepSummaryRead(BaseModel):
    sweep_name: str
    artifact: str
    summary: dict[str, Any]


class LocalBacktestSweepResultsRead(BaseModel):
    sweep_name: str
    artifact: str
    items: list[LocalBacktestSweepResultRead]
