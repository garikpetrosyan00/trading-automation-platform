from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.draft_balance import DraftBalance
from app.models.execution_attempt import ExecutionAttempt
from app.models.paper_equity_snapshot import PaperEquitySnapshot
from app.models.paper_position import PaperPosition
from app.models.run_event import RunEvent
from app.models.simulated_fill import SimulatedFill
from app.models.simulated_order import SimulatedOrder
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.run_event import RunEventRepository


ISSUE_DESCRIPTIONS = {
    "filled_attempt_missing_order": "A filled paper attempt is missing its filled paper order.",
    "filled_order_missing_fill": "A filled paper order is missing its paper fill.",
    "filled_attempt_missing_equity_snapshot": "A filled paper attempt is missing its paper equity snapshot.",
    "filled_buy_missing_draft_balance": "A filled paper BUY is missing its quote Draft Balance row.",
    "filled_buy_missing_paper_position": "A filled paper BUY is missing its Paper Position row.",
    "filled_sell_missing_draft_balance": "A filled paper SELL is missing its quote Draft Balance row.",
    "filled_sell_missing_paper_position": "A filled paper SELL is missing its Paper Position row.",
    "rejected_attempt_has_order": "A rejected paper attempt is linked to a paper order.",
    "rejected_attempt_has_fill": "A rejected paper attempt is linked to a paper fill.",
    "rejected_attempt_has_filled_attempt": "A rejected paper attempt has an unexpected filled paper attempt in the same bot scope.",
    "rejected_attempt_has_equity_snapshot": "A rejected paper attempt is linked to a paper equity snapshot.",
    "duplicate_filled_attempt_for_order": "Multiple filled paper attempts reference the same paper order.",
    "run_event_missing_for_filled_attempt": "A filled paper attempt is missing a matching order_filled RunEvent.",
    "run_event_missing_for_rejected_attempt": "A rejected paper attempt is missing a matching order_rejected RunEvent.",
}

QUOTE_ASSET_SUFFIXES = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH")
ZERO = Decimal("0")


@dataclass(frozen=True)
class PaperReconciliationIssue:
    code: str
    description: str
    severity: str = "warning"
    symbol: str | None = None
    side: str | None = None
    artifact: str | None = None


@dataclass(frozen=True)
class PaperReconciliationAuditResult:
    bot_id: int
    ok: bool
    issues: list[PaperReconciliationIssue]
    checked_attempt_count: int
    checked_order_count: int
    checked_fill_count: int
    checked_run_event_count: int
    checked_equity_snapshot_count: int
    read_only: bool = True


class PaperReconciliationAuditService:
    """Read-only consistency checks for bot-scoped paper execution artifacts."""

    def __init__(
        self,
        *,
        db: Session,
        attempt_repository: ExecutionAttemptRepository,
        portfolio_repository: PortfolioRepository,
        draft_balance_repository: DraftBalanceRepository,
        paper_position_repository: PaperPositionRepository,
        paper_equity_snapshot_repository: PaperEquitySnapshotRepository,
        run_event_repository: RunEventRepository,
    ):
        self.db = db
        self.attempt_repository = attempt_repository
        self.portfolio_repository = portfolio_repository
        self.draft_balance_repository = draft_balance_repository
        self.paper_position_repository = paper_position_repository
        self.paper_equity_snapshot_repository = paper_equity_snapshot_repository
        self.run_event_repository = run_event_repository

    def audit_bot(self, *, bot_id: int, limit: int = 100) -> PaperReconciliationAuditResult:
        attempts = self.attempt_repository.list_filtered(bot_id=bot_id, mode="paper", limit=limit)
        orders = self.portfolio_repository.list_orders_filtered(bot_id=bot_id, mode="paper", limit=limit)
        fills = self._list_bot_fills(bot_id=bot_id, limit=limit)
        snapshots = self.paper_equity_snapshot_repository.list_latest_for_bot(bot_id=bot_id, limit=limit)
        run_events = self.run_event_repository.list_for_bot(bot_id)
        draft_balances = self.draft_balance_repository.list_for_bot(bot_id)
        paper_positions = self._list_bot_positions(bot_id=bot_id)

        issues: list[PaperReconciliationIssue] = []
        orders_by_id = {order.id: order for order in orders}
        fills_by_order_id: dict[int, list[SimulatedFill]] = {}
        for fill in fills:
            fills_by_order_id.setdefault(fill.order_id, []).append(fill)
        snapshots_by_order_id = {
            snapshot.source_order_id: snapshot for snapshot in snapshots if snapshot.source_order_id is not None
        }
        snapshots_by_fill_id = {
            snapshot.source_fill_id: snapshot for snapshot in snapshots if snapshot.source_fill_id is not None
        }
        draft_assets = {row.asset: row for row in draft_balances}
        positions_by_symbol = {position.symbol: position for position in paper_positions}

        for attempt in attempts:
            if attempt.final_status == "filled":
                self._audit_filled_attempt(
                    attempt=attempt,
                    orders_by_id=orders_by_id,
                    fills_by_order_id=fills_by_order_id,
                    snapshots_by_order_id=snapshots_by_order_id,
                    snapshots_by_fill_id=snapshots_by_fill_id,
                    draft_assets=draft_assets,
                    positions_by_symbol=positions_by_symbol,
                    run_events=run_events,
                    issues=issues,
                )
            elif attempt.final_status == "rejected_by_broker":
                self._audit_rejected_attempt(
                    attempt=attempt,
                    orders_by_id=orders_by_id,
                    fills_by_order_id=fills_by_order_id,
                    snapshots_by_order_id=snapshots_by_order_id,
                    snapshots_by_fill_id=snapshots_by_fill_id,
                    attempts=attempts,
                    run_events=run_events,
                    issues=issues,
                )

        self._audit_duplicate_filled_attempts(attempts=attempts, issues=issues)
        return PaperReconciliationAuditResult(
            bot_id=bot_id,
            ok=not issues,
            issues=issues,
            checked_attempt_count=len(attempts),
            checked_order_count=len(orders),
            checked_fill_count=len(fills),
            checked_run_event_count=len(run_events),
            checked_equity_snapshot_count=len(snapshots),
        )

    def _audit_filled_attempt(
        self,
        *,
        attempt: ExecutionAttempt,
        orders_by_id: dict[int, SimulatedOrder],
        fills_by_order_id: dict[int, list[SimulatedFill]],
        snapshots_by_order_id: dict[int, PaperEquitySnapshot],
        snapshots_by_fill_id: dict[int, PaperEquitySnapshot],
        draft_assets: dict[str, DraftBalance],
        positions_by_symbol: dict[str, PaperPosition],
        run_events: list[RunEvent],
        issues: list[PaperReconciliationIssue],
    ) -> None:
        order = orders_by_id.get(attempt.order_id) if attempt.order_id is not None else None
        if order is None or order.status != "filled" or order.side != attempt.side:
            issues.append(self._issue("filled_attempt_missing_order", attempt, artifact="order"))
            return

        fills = fills_by_order_id.get(order.id, [])
        if not fills:
            issues.append(self._issue("filled_order_missing_fill", attempt, artifact="fill"))
            return

        fill = fills[0]
        snapshot = snapshots_by_fill_id.get(fill.id) or snapshots_by_order_id.get(order.id)
        expected_event_type = f"{attempt.side}_fill"
        if snapshot is None or snapshot.event_type != expected_event_type:
            issues.append(self._issue("filled_attempt_missing_equity_snapshot", attempt, artifact="paper_equity_snapshot"))

        _base_asset, quote_asset = self._symbol_assets(attempt.symbol)
        if attempt.side == "buy":
            if quote_asset not in draft_assets:
                issues.append(self._issue("filled_buy_missing_draft_balance", attempt, artifact="draft_balance"))
            position = positions_by_symbol.get(attempt.symbol)
            if position is None and (snapshot is None or snapshot.base_quantity <= ZERO):
                issues.append(self._issue("filled_buy_missing_paper_position", attempt, artifact="paper_position"))
        elif attempt.side == "sell":
            if quote_asset not in draft_assets:
                issues.append(self._issue("filled_sell_missing_draft_balance", attempt, artifact="draft_balance"))
            if attempt.symbol not in positions_by_symbol and (snapshot is None or snapshot.base_quantity != ZERO):
                issues.append(self._issue("filled_sell_missing_paper_position", attempt, artifact="paper_position"))

        if not self._has_matching_run_event(run_events, message="order_filled", attempt=attempt):
            issues.append(self._issue("run_event_missing_for_filled_attempt", attempt, artifact="run_event"))

    def _audit_rejected_attempt(
        self,
        *,
        attempt: ExecutionAttempt,
        orders_by_id: dict[int, SimulatedOrder],
        fills_by_order_id: dict[int, list[SimulatedFill]],
        snapshots_by_order_id: dict[int, PaperEquitySnapshot],
        snapshots_by_fill_id: dict[int, PaperEquitySnapshot],
        attempts: list[ExecutionAttempt],
        run_events: list[RunEvent],
        issues: list[PaperReconciliationIssue],
    ) -> None:
        if attempt.order_id is not None:
            issues.append(self._issue("rejected_attempt_has_order", attempt, artifact="order"))
            if attempt.order_id in fills_by_order_id:
                issues.append(self._issue("rejected_attempt_has_fill", attempt, artifact="fill"))
            if attempt.order_id in snapshots_by_order_id:
                issues.append(self._issue("rejected_attempt_has_equity_snapshot", attempt, artifact="paper_equity_snapshot"))

        metadata = attempt.metadata_ or {}
        fill_id = metadata.get("fill_id")
        if fill_id is not None:
            issues.append(self._issue("rejected_attempt_has_fill", attempt, artifact="fill"))
            if fill_id in snapshots_by_fill_id:
                issues.append(self._issue("rejected_attempt_has_equity_snapshot", attempt, artifact="paper_equity_snapshot"))

        if any(
            other.id != attempt.id
            and other.final_status == "filled"
            and other.symbol == attempt.symbol
            and other.side == attempt.side
            and other.created_at == attempt.created_at
            for other in attempts
        ):
            issues.append(self._issue("rejected_attempt_has_filled_attempt", attempt, artifact="execution_attempt"))

        if not self._has_matching_run_event(run_events, message="order_rejected", attempt=attempt):
            issues.append(self._issue("run_event_missing_for_rejected_attempt", attempt, artifact="run_event"))

    def _audit_duplicate_filled_attempts(
        self,
        *,
        attempts: list[ExecutionAttempt],
        issues: list[PaperReconciliationIssue],
    ) -> None:
        seen_order_ids: set[int] = set()
        duplicate_order_ids: set[int] = set()
        for attempt in attempts:
            if attempt.final_status != "filled" or attempt.order_id is None:
                continue
            if attempt.order_id in seen_order_ids:
                duplicate_order_ids.add(attempt.order_id)
            seen_order_ids.add(attempt.order_id)

        for order_id in duplicate_order_ids:
            attempt = next(item for item in attempts if item.order_id == order_id and item.final_status == "filled")
            issues.append(self._issue("duplicate_filled_attempt_for_order", attempt, artifact="execution_attempt"))

    @staticmethod
    def _has_matching_run_event(run_events: list[RunEvent], *, message: str, attempt: ExecutionAttempt) -> bool:
        for event in run_events:
            payload = event.payload or {}
            if event.message != message:
                continue
            if payload.get("side") != attempt.side or payload.get("symbol") != attempt.symbol:
                continue
            if message == "order_rejected" and payload.get("message") != attempt.final_reason:
                continue
            return True
        return False

    def _list_bot_fills(self, *, bot_id: int, limit: int) -> list[SimulatedFill]:
        statement = (
            select(SimulatedFill)
            .join(SimulatedOrder, SimulatedOrder.id == SimulatedFill.order_id)
            .where(SimulatedOrder.bot_id == bot_id, SimulatedOrder.mode == "paper")
            .order_by(SimulatedFill.created_at.desc(), SimulatedFill.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def _list_bot_positions(self, *, bot_id: int) -> list[PaperPosition]:
        statement = select(PaperPosition).where(PaperPosition.bot_id == bot_id).order_by(PaperPosition.symbol.asc())
        return list(self.db.scalars(statement).all())

    @classmethod
    def _issue(cls, code: str, attempt: ExecutionAttempt, *, artifact: str) -> PaperReconciliationIssue:
        return PaperReconciliationIssue(
            code=code,
            description=ISSUE_DESCRIPTIONS[code],
            symbol=attempt.symbol,
            side=attempt.side,
            artifact=artifact,
        )

    @staticmethod
    def _symbol_assets(symbol: str) -> tuple[str, str]:
        normalized = symbol.strip().upper()
        for quote_asset in QUOTE_ASSET_SUFFIXES:
            if normalized.endswith(quote_asset) and len(normalized) > len(quote_asset):
                return normalized[: -len(quote_asset)], quote_asset
        return normalized, "USDT"
