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
MONEY_QUANTUM = Decimal("0.00000001")
DEFAULT_PAPER_ACCOUNT_CURRENCY = "USDT"


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
        account = self.repository.get_account()
        positions = self.repository.list_positions(include_closed=False)
        position_reads: list[PaperPortfolioPositionRead] = []
        total_realized_pnl = ZERO
        total_market_value = ZERO
        total_unrealized_pnl = ZERO

        for position in self.repository.list_positions(include_closed=True):
            total_realized_pnl += position.realized_pnl

        for position in positions:
            latest_price = self._get_latest_price(position.symbol)
            market_value = None
            unrealized_pnl = None
            unrealized_pnl_percent = None
            if latest_price is None:
                price_available = False
            else:
                price_available = True
                market_value = self._quantize_money(position.quantity * latest_price)
                cost_basis = position.quantity * position.average_entry_price
                unrealized_pnl = self._quantize_money(market_value - cost_basis)
                if cost_basis > ZERO:
                    unrealized_pnl_percent = (unrealized_pnl / cost_basis) * Decimal("100")
                total_market_value += market_value
                total_unrealized_pnl += unrealized_pnl

            position_reads.append(
                PaperPortfolioPositionRead(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    average_entry_price=position.average_entry_price,
                    latest_price=latest_price,
                    latest_market_price=latest_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_percent,
                    realized_pnl=position.realized_pnl,
                    price_available=price_available,
                    updated_at=position.updated_at,
                )
            )

        account_currency = account.base_currency if account is not None else DEFAULT_PAPER_ACCOUNT_CURRENCY
        cash_balance = account.cash_balance if account is not None else ZERO
        starting_balance = account.starting_cash if account is not None else ZERO
        updated_at = account.updated_at if account is not None else None

        return PaperPortfolioSnapshotRead(
            base_currency=account_currency,
            account_currency=account_currency,
            starting_balance=starting_balance,
            cash_balance=cash_balance,
            total_realized_pnl=total_realized_pnl,
            positions=position_reads,
            positions_market_value=self._quantize_money(total_market_value),
            total_market_value=self._quantize_money(total_market_value),
            total_unrealized_pnl=self._quantize_money(total_unrealized_pnl),
            total_equity=self._quantize_money(cash_balance + total_market_value),
            open_position_count=len(position_reads),
            updated_at=updated_at,
        )

    def reset_paper_portfolio(self, starting_balance: Decimal) -> PaperPortfolioResetRead:
        if not starting_balance.is_finite() or starting_balance <= ZERO:
            raise ValueError("Paper starting balance must be a positive decimal")

        account = self.repository.get_account_for_update()
        if account is None:
            raise ValueError("Portfolio account is not initialized")
        try:
            if self.repository.has_open_positions():
                raise ConflictError(
                    "Paper portfolio reset is only allowed when all positions are flat",
                    error_code="paper_portfolio_not_flat",
                )
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

    @staticmethod
    def _quantize_money(value: Decimal) -> Decimal:
        if value == ZERO:
            return ZERO
        return value.quantize(MONEY_QUANTUM)
