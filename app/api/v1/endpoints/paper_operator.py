from dataclasses import asdict

from fastapi import APIRouter

from app.api.dependencies import DbSession
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.schemas.paper_operator import PaperOperatorOverviewRead
from app.services.paper_operator_overview import PaperOperatorOverviewService
from app.services.paper_reconciliation_audit import PaperReconciliationAuditService

router = APIRouter()


@router.get("/bots/{bot_id}/paper/operator-overview", response_model=PaperOperatorOverviewRead)
async def get_bot_paper_operator_overview(bot_id: int, db: DbSession) -> PaperOperatorOverviewRead:
    bot = BotRepository(db).get_by_id(bot_id)
    if bot is None:
        raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

    attempt_repository = ExecutionAttemptRepository(db)
    portfolio_repository = PortfolioRepository(db)
    draft_balance_repository = DraftBalanceRepository(db)
    paper_position_repository = PaperPositionRepository(db)
    paper_equity_snapshot_repository = PaperEquitySnapshotRepository(db)
    run_event_repository = RunEventRepository(db)
    audit_service = PaperReconciliationAuditService(
        db=db,
        attempt_repository=attempt_repository,
        portfolio_repository=portfolio_repository,
        draft_balance_repository=draft_balance_repository,
        paper_position_repository=paper_position_repository,
        paper_equity_snapshot_repository=paper_equity_snapshot_repository,
        run_event_repository=run_event_repository,
    )
    overview = PaperOperatorOverviewService(
        settings=get_settings(),
        draft_balance_repository=draft_balance_repository,
        paper_position_repository=paper_position_repository,
        paper_equity_snapshot_repository=paper_equity_snapshot_repository,
        execution_attempt_repository=attempt_repository,
        run_event_repository=run_event_repository,
        reconciliation_audit_service=audit_service,
    ).get_overview(bot=bot)
    payload = asdict(overview)
    audit_payload = payload["latest_reconciliation_audit"]
    audit_payload.pop("bot_id", None)
    audit_payload["issue_count"] = len(audit_payload["issues"])
    return PaperOperatorOverviewRead(**payload)
