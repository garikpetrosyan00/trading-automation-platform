from decimal import Decimal

from app.data.schemas import MarketEvent
from app.core.errors import ConflictError
from app.models.portfolio_account import PortfolioAccount
from app.models.position import Position
from app.repositories.portfolio import PortfolioRepository
from app.schemas.portfolio import (
    PaperPortfolioPositionRead,
    PaperPortfolioResetRead,
    PaperPortfolioSnapshotRead,
    PortfolioSummaryRead,
    PositionRead,
)

ZERO = Decimal("0")


class PortfolioService:
    def __init__(self, repository: PortfolioRepository, market_data_service):
        self.repository = repository
        self.market_data_service = market_data_service

    def get_account(self) -> PortfolioAccount:
        account = self.repository.get_account()
        if account is None:
            raise ValueError("Portfolio account is not initialized")
        return account

    def list_positions(self) -> list[PositionRead]:
        positions = self.repository.list_positions(include_closed=False)
        return [self._build_position_read(position) for position in positions]

    def get_summary(self) -> PortfolioSummaryRead:
        account = self.get_account()
        positions = self.repository.list_positions(include_closed=True)

        market_value = ZERO
        unrealized_pnl = ZERO
        realized_pnl = ZERO

        for position in positions:
            realized_pnl += position.realized_pnl
            if position.quantity <= ZERO:
                continue

            latest_price = self._get_latest_price(position.symbol)
            if latest_price is None:
                continue

            position_market_value = position.quantity * latest_price
            position_cost_basis = position.quantity * position.average_entry_price
            market_value += position_market_value
            unrealized_pnl += position_market_value - position_cost_basis

        return PortfolioSummaryRead(
            base_currency=account.base_currency,
            starting_cash=account.starting_cash,
            cash_balance=account.cash_balance,
            market_value=market_value,
            equity=account.cash_balance + market_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
        )

    def get_paper_snapshot(self) -> PaperPortfolioSnapshotRead:
        account = self.get_account()
        positions = self.repository.list_positions(include_closed=False)
        position_reads: list[PaperPortfolioPositionRead] = []
        total_realized_pnl = ZERO
        total_market_value = ZERO
        total_unrealized_pnl = ZERO
        all_market_values_available = True

        for position in self.repository.list_positions(include_closed=True):
            total_realized_pnl += position.realized_pnl

        for position in positions:
            latest_price = self._get_latest_price(position.symbol)
            market_value = None
            unrealized_pnl = None
            if latest_price is None:
                all_market_values_available = False
            else:
                market_value = position.quantity * latest_price
                unrealized_pnl = market_value - (position.quantity * position.average_entry_price)
                total_market_value += market_value
                total_unrealized_pnl += unrealized_pnl

            position_reads.append(
                PaperPortfolioPositionRead(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    average_entry_price=position.average_entry_price,
                    latest_price=latest_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=position.realized_pnl,
                    updated_at=position.updated_at,
                )
            )

        return PaperPortfolioSnapshotRead(
            base_currency=account.base_currency,
            starting_balance=account.starting_cash,
            cash_balance=account.cash_balance,
            total_realized_pnl=total_realized_pnl,
            positions=position_reads,
            total_market_value=total_market_value if all_market_values_available else None,
            total_unrealized_pnl=total_unrealized_pnl if all_market_values_available else None,
            total_equity=account.cash_balance + total_market_value if all_market_values_available else None,
            updated_at=account.updated_at,
        )

    def reset_paper_portfolio(self, starting_balance: Decimal) -> PaperPortfolioResetRead:
        if not starting_balance.is_finite() or starting_balance <= ZERO:
            raise ValueError("Paper starting balance must be a positive decimal")
        if self.repository.has_open_positions():
            raise ConflictError(
                "Paper portfolio reset is only allowed when all positions are flat",
                error_code="paper_portfolio_not_flat",
            )

        account = self.get_account()
        try:
            self.repository.reset_account(account, starting_balance)
            self.repository.reset_position_session_state()
            self.repository.commit()
            self.repository.refresh(account)
        except Exception:
            self.repository.rollback()
            raise

        return PaperPortfolioResetRead(
            base_currency=account.base_currency,
            starting_balance=account.starting_cash,
            cash_balance=account.cash_balance,
            total_realized_pnl=ZERO,
            reset_at=account.updated_at,
        )

    def _build_position_read(self, position: Position) -> PositionRead:
        latest_price = self._get_latest_price(position.symbol)
        market_value = ZERO
        unrealized_pnl = ZERO

        if latest_price is not None:
            market_value = position.quantity * latest_price
            unrealized_pnl = market_value - (position.quantity * position.average_entry_price)

        return PositionRead(
            id=position.id,
            symbol=position.symbol,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            latest_price=latest_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=position.realized_pnl,
            updated_at=position.updated_at,
        )

    def _get_latest_price(self, symbol: str) -> Decimal | None:
        latest = self.market_data_service.get_latest(symbol)
        if latest is None or not isinstance(latest, MarketEvent):
            return None
        return latest.price or latest.close
