from pydantic import BaseModel, Field


class PaperReconciliationIssueRead(BaseModel):
    code: str
    description: str
    severity: str
    symbol: str | None = None
    side: str | None = None
    artifact: str | None = None


class PaperReconciliationAuditRead(BaseModel):
    bot_id: int
    ok: bool
    issues: list[PaperReconciliationIssueRead] = Field(default_factory=list)
    checked_attempt_count: int
    checked_order_count: int
    checked_fill_count: int
    checked_run_event_count: int
    checked_equity_snapshot_count: int
    read_only: bool
