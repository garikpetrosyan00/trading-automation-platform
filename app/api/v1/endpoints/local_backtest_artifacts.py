from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.schemas.local_backtest_artifacts import (
    LocalBacktestBundleCatalogRead,
    LocalBacktestBundleManifestRead,
    LocalBacktestRunCatalogRead,
    LocalBacktestSummaryRead,
    LocalBacktestSweepCatalogRead,
    LocalBacktestSweepResultsRead,
    LocalBacktestSweepSummaryRead,
)
from app.services.local_backtest_artifacts import LocalBacktestArtifactService

router = APIRouter(prefix="/local-demo")


def get_local_backtest_artifact_service() -> LocalBacktestArtifactService:
    return LocalBacktestArtifactService()


LocalBacktestArtifactServiceDep = Annotated[LocalBacktestArtifactService, Depends(get_local_backtest_artifact_service)]


@router.get("/runs", response_model=LocalBacktestRunCatalogRead)
async def list_local_backtest_runs(service: LocalBacktestArtifactServiceDep) -> dict:
    return service.list_runs()


@router.get("/bundles", response_model=LocalBacktestBundleCatalogRead)
async def list_local_backtest_bundles(service: LocalBacktestArtifactServiceDep) -> dict:
    return service.list_bundles()


@router.get("/sweeps", response_model=LocalBacktestSweepCatalogRead)
async def list_local_backtest_sweeps(service: LocalBacktestArtifactServiceDep) -> dict:
    return service.list_sweeps()


@router.get("/runs/{run_name}/summary", response_model=LocalBacktestSummaryRead)
async def get_local_backtest_run_summary(
    run_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> dict:
    return service.read_run_summary(run_name)


@router.get("/runs/{run_name}/report", response_class=Response)
async def get_local_backtest_run_report(
    run_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> Response:
    markdown = service.read_run_report_markdown(run_name)
    return Response(content=markdown, media_type="text/markdown; charset=utf-8")


@router.get("/bundles/{bundle_name}/manifest", response_model=LocalBacktestBundleManifestRead)
async def get_local_backtest_bundle_manifest(
    bundle_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> dict:
    return service.read_bundle_manifest(bundle_name)


@router.get("/sweeps/{sweep_name}/summary", response_model=LocalBacktestSweepSummaryRead)
async def get_local_backtest_sweep_summary(
    sweep_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> dict:
    return service.read_sweep_summary(sweep_name)


@router.get("/sweeps/{sweep_name}/results", response_model=LocalBacktestSweepResultsRead)
async def get_local_backtest_sweep_results(
    sweep_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> dict:
    return service.read_sweep_results(sweep_name)


@router.get("/sweeps/{sweep_name}/report", response_class=Response)
async def get_local_backtest_sweep_report(
    sweep_name: str,
    service: LocalBacktestArtifactServiceDep,
) -> Response:
    markdown = service.read_sweep_report_markdown(sweep_name)
    return Response(content=markdown, media_type="text/markdown; charset=utf-8")
