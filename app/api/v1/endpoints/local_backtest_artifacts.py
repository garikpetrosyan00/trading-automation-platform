from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.schemas.local_backtest_artifacts import LocalBacktestBundleManifestRead, LocalBacktestSummaryRead
from app.services.local_backtest_artifacts import LocalBacktestArtifactService

router = APIRouter(prefix="/local-demo")


def get_local_backtest_artifact_service() -> LocalBacktestArtifactService:
    return LocalBacktestArtifactService()


LocalBacktestArtifactServiceDep = Annotated[LocalBacktestArtifactService, Depends(get_local_backtest_artifact_service)]


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
