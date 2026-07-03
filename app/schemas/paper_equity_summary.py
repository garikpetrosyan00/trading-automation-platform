from pydantic import BaseModel

from app.schemas.paper_operator import PaperOperatorEquitySnapshotRead


class PaperEquitySummaryRead(BaseModel):
    bot_id: int
    mode: str
    status: str
    paper_trading_enabled: bool
    starting_cash: str
    current_cash: str
    open_position_count: int
    open_positions_value: str
    latest_total_equity: str | None
    realized_pnl: str
    unrealized_pnl: str
    total_pnl: str
    equity_snapshot_count: int
    latest_snapshot: PaperOperatorEquitySnapshotRead | None = None
    read_only: bool
