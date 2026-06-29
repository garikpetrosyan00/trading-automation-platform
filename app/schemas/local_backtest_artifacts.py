from typing import Any

from pydantic import BaseModel


class LocalBacktestSummaryRead(BaseModel):
    run_name: str
    artifact: str
    summary: dict[str, Any]


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
