from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.paper_reconciliation import PaperReconciliationIssueRead


class PaperOperatorDraftBalanceAssetRead(BaseModel):
    asset: str
    available: str
    locked: str
    total: str


class PaperOperatorDraftBalanceRead(BaseModel):
    assets: list[PaperOperatorDraftBalanceAssetRead] = Field(default_factory=list)


class PaperOperatorPositionRead(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    quantity: str
    average_entry_price: str
    realized_pnl: str
    updated_at: datetime | None = None


class PaperOperatorEquitySnapshotRead(BaseModel):
    symbol: str
    quote_asset: str
    cash_available: str
    cash_locked: str
    base_quantity: str
    base_locked: str
    average_entry_price: str
    realized_pnl: str
    market_price: str | None = None
    position_value: str | None = None
    total_equity: str | None = None
    event_type: str
    created_at: datetime


class PaperOperatorExecutionSummaryRead(BaseModel):
    recent_attempt_count: int
    filled_attempt_count: int
    rejected_attempt_count: int
    latest_attempt_status: str | None = None
    latest_attempt_reason: str | None = None
    latest_run_event_message: str | None = None


class PaperOperatorReconciliationAuditRead(BaseModel):
    ok: bool
    issue_count: int
    issues: list[PaperReconciliationIssueRead] = Field(default_factory=list)
    checked_attempt_count: int
    checked_order_count: int
    checked_fill_count: int
    checked_run_event_count: int
    checked_equity_snapshot_count: int
    read_only: bool


class PaperOperatorOverviewRead(BaseModel):
    bot_id: int
    mode: str
    status: str
    paper_trading_enabled: bool
    draft_balance: PaperOperatorDraftBalanceRead
    paper_positions: list[PaperOperatorPositionRead] = Field(default_factory=list)
    latest_equity_snapshot: PaperOperatorEquitySnapshotRead | None = None
    recent_execution_summary: PaperOperatorExecutionSummaryRead
    latest_reconciliation_audit: PaperOperatorReconciliationAuditRead
    read_only: bool
