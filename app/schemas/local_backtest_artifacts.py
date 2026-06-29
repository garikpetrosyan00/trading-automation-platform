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
