from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.config import Settings
from app.models.bot import Bot
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_equity_snapshot import PaperEquitySnapshot
from app.models.paper_position import PaperPosition
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository
from app.services.paper_reconciliation_audit import PaperReconciliationAuditResult, PaperReconciliationAuditService


@dataclass(frozen=True)
class PaperOperatorDraftAsset:
    asset: str
    available: str
    locked: str
    total: str


@dataclass(frozen=True)
class PaperOperatorDraftBalance:
    assets: list[PaperOperatorDraftAsset]


@dataclass(frozen=True)
class PaperOperatorPosition:
    symbol: str
    base_asset: str
    quote_asset: str
    quantity: str
    average_entry_price: str
    realized_pnl: str
    updated_at: datetime | None


@dataclass(frozen=True)
class PaperOperatorEquitySnapshot:
    symbol: str
    quote_asset: str
    cash_available: str
    cash_locked: str
    base_quantity: str
    base_locked: str
    average_entry_price: str
    realized_pnl: str
    market_price: str | None
    position_value: str | None
    total_equity: str | None
    event_type: str
    created_at: datetime


@dataclass(frozen=True)
class PaperOperatorExecutionSummary:
    recent_attempt_count: int
    filled_attempt_count: int
    rejected_attempt_count: int
    latest_attempt_status: str | None
    latest_attempt_reason: str | None
    latest_run_event_message: str | None


@dataclass(frozen=True)
class PaperOperatorOverview:
    bot_id: int
    mode: str
    status: str
    paper_trading_enabled: bool
    draft_balance: PaperOperatorDraftBalance
    paper_positions: list[PaperOperatorPosition]
    latest_equity_snapshot: PaperOperatorEquitySnapshot | None
    recent_execution_summary: PaperOperatorExecutionSummary
    latest_reconciliation_audit: PaperReconciliationAuditResult
    read_only: bool = True


class PaperOperatorOverviewService:
    """Read-only operator summary for one bot's paper trading state."""

    def __init__(
        self,
        *,
        settings: Settings,
        draft_balance_repository: DraftBalanceRepository,
        paper_position_repository: PaperPositionRepository,
        paper_equity_snapshot_repository: PaperEquitySnapshotRepository,
        execution_attempt_repository: ExecutionAttemptRepository,
        run_event_repository: RunEventRepository,
        reconciliation_audit_service: PaperReconciliationAuditService,
    ):
        self.settings = settings
        self.draft_balance_repository = draft_balance_repository
        self.paper_position_repository = paper_position_repository
        self.paper_equity_snapshot_repository = paper_equity_snapshot_repository
        self.execution_attempt_repository = execution_attempt_repository
        self.run_event_repository = run_event_repository
        self.reconciliation_audit_service = reconciliation_audit_service

    def get_overview(self, *, bot: Bot, recent_limit: int = 20) -> PaperOperatorOverview:
        attempts = self.execution_attempt_repository.list_filtered(
            bot_id=bot.id,
            mode="paper",
            limit=recent_limit,
        )
        latest_event = self.run_event_repository.list_recent_for_bot(bot.id, limit=1)
        snapshots = self.paper_equity_snapshot_repository.list_latest_for_bot(bot_id=bot.id, limit=1)
        audit = self.reconciliation_audit_service.audit_bot(bot_id=bot.id, limit=recent_limit)

        return PaperOperatorOverview(
            bot_id=bot.id,
            mode=bot.execution_mode or ("paper" if bot.is_paper else "live"),
            status=bot.status,
            paper_trading_enabled=self.settings.paper_trading_enabled,
            draft_balance=self._draft_balance(bot_id=bot.id),
            paper_positions=[
                self._position_to_summary(position)
                for position in self.paper_position_repository.list_for_bot(bot_id=bot.id)
            ],
            latest_equity_snapshot=self._snapshot_to_summary(snapshots[0]) if snapshots else None,
            recent_execution_summary=self._execution_summary(
                attempts,
                latest_run_event_message=latest_event[0].message if latest_event else None,
            ),
            latest_reconciliation_audit=audit,
        )

    def _draft_balance(self, *, bot_id: int) -> PaperOperatorDraftBalance:
        assets = []
        for row in self.draft_balance_repository.list_for_bot(bot_id):
            assets.append(
                PaperOperatorDraftAsset(
                    asset=row.asset,
                    available=_decimal_to_string(row.available),
                    locked=_decimal_to_string(row.locked),
                    total=_decimal_to_string(row.available + row.locked),
                )
            )
        return PaperOperatorDraftBalance(assets=assets)

    @staticmethod
    def _position_to_summary(position: PaperPosition) -> PaperOperatorPosition:
        return PaperOperatorPosition(
            symbol=position.symbol,
            base_asset=position.base_asset,
            quote_asset=position.quote_asset,
            quantity=_decimal_to_string(position.quantity),
            average_entry_price=_decimal_to_string(position.average_entry_price),
            realized_pnl=_decimal_to_string(position.realized_pnl),
            updated_at=position.updated_at,
        )

    @staticmethod
    def _snapshot_to_summary(snapshot: PaperEquitySnapshot) -> PaperOperatorEquitySnapshot:
        return PaperOperatorEquitySnapshot(
            symbol=snapshot.symbol,
            quote_asset=snapshot.quote_asset,
            cash_available=_decimal_to_string(snapshot.cash_available),
            cash_locked=_decimal_to_string(snapshot.cash_locked),
            base_quantity=_decimal_to_string(snapshot.base_quantity),
            base_locked=_decimal_to_string(snapshot.base_locked),
            average_entry_price=_decimal_to_string(snapshot.average_entry_price),
            realized_pnl=_decimal_to_string(snapshot.realized_pnl),
            market_price=_optional_decimal_to_string(snapshot.market_price),
            position_value=_optional_decimal_to_string(snapshot.position_value),
            total_equity=_optional_decimal_to_string(snapshot.total_equity),
            event_type=snapshot.event_type,
            created_at=snapshot.created_at,
        )

    @staticmethod
    def _execution_summary(
        attempts: list[ExecutionAttempt],
        *,
        latest_run_event_message: str | None,
    ) -> PaperOperatorExecutionSummary:
        latest_attempt = attempts[0] if attempts else None
        return PaperOperatorExecutionSummary(
            recent_attempt_count=len(attempts),
            filled_attempt_count=sum(1 for attempt in attempts if attempt.final_status == "filled"),
            rejected_attempt_count=sum(1 for attempt in attempts if attempt.final_status == "rejected_by_broker"),
            latest_attempt_status=latest_attempt.final_status if latest_attempt is not None else None,
            latest_attempt_reason=latest_attempt.final_reason if latest_attempt is not None else None,
            latest_run_event_message=latest_run_event_message,
        )


def _decimal_to_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _optional_decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _decimal_to_string(value)
