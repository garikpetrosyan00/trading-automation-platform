from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings
from app.models.bot import Bot
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.services.paper_operator_overview import PaperOperatorEquitySnapshot


@dataclass(frozen=True)
class PaperEquitySummary:
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
    latest_snapshot: PaperOperatorEquitySnapshot | None
    read_only: bool = True


class PaperEquitySummaryService:
    """Read-only paper equity reporting summary for one bot."""

    def __init__(
        self,
        *,
        settings: Settings,
        draft_balance_repository: DraftBalanceRepository,
        paper_position_repository: PaperPositionRepository,
        paper_equity_snapshot_repository: PaperEquitySnapshotRepository,
    ):
        self.settings = settings
        self.draft_balance_repository = draft_balance_repository
        self.paper_position_repository = paper_position_repository
        self.paper_equity_snapshot_repository = paper_equity_snapshot_repository

    def get_summary(self, *, bot: Bot) -> PaperEquitySummary:
        positions = self.paper_position_repository.list_for_bot(bot_id=bot.id)
        latest_snapshots = self.paper_equity_snapshot_repository.list_latest_for_bot(bot_id=bot.id, limit=1)
        latest_snapshot = latest_snapshots[0] if latest_snapshots else None

        current_cash = (
            latest_snapshot.cash_available + latest_snapshot.cash_locked
            if latest_snapshot is not None
            else self._cash_from_draft_balance(bot_id=bot.id)
        )
        open_positions = [position for position in positions if position.quantity > 0]
        open_positions_value = sum(
            (position.quantity * position.average_entry_price for position in open_positions),
            Decimal("0"),
        )
        realized_pnl = sum((position.realized_pnl for position in positions), Decimal("0"))
        unrealized_pnl = Decimal("0")
        if latest_snapshot is not None and latest_snapshot.market_price is not None:
            unrealized_pnl = sum(
                (
                    position.quantity * (latest_snapshot.market_price - position.average_entry_price)
                    for position in open_positions
                    if position.symbol == latest_snapshot.symbol
                ),
                Decimal("0"),
            )
        total_pnl = realized_pnl + unrealized_pnl
        latest_total_equity = latest_snapshot.total_equity if latest_snapshot is not None else None
        starting_cash = latest_total_equity - total_pnl if latest_total_equity is not None else Decimal("0")

        return PaperEquitySummary(
            bot_id=bot.id,
            mode=bot.execution_mode or ("paper" if bot.is_paper else "live"),
            status=bot.status,
            paper_trading_enabled=self.settings.paper_trading_enabled,
            starting_cash=_decimal_to_string(starting_cash),
            current_cash=_decimal_to_string(current_cash),
            open_position_count=len(open_positions),
            open_positions_value=_decimal_to_string(open_positions_value),
            latest_total_equity=_optional_decimal_to_string(latest_total_equity),
            realized_pnl=_decimal_to_string(realized_pnl),
            unrealized_pnl=_decimal_to_string(unrealized_pnl),
            total_pnl=_decimal_to_string(total_pnl),
            equity_snapshot_count=self.paper_equity_snapshot_repository.count_for_bot(bot_id=bot.id),
            latest_snapshot=_snapshot_to_summary(latest_snapshot) if latest_snapshot is not None else None,
        )

    def _cash_from_draft_balance(self, *, bot_id: int) -> Decimal:
        return sum(
            (row.available + row.locked for row in self.draft_balance_repository.list_for_bot(bot_id)),
            Decimal("0"),
        )


def _snapshot_to_summary(snapshot) -> PaperOperatorEquitySnapshot:
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


def _decimal_to_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _optional_decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _decimal_to_string(value)
