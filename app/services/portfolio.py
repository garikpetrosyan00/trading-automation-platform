from decimal import Decimal

from app.data.schemas import MarketEvent
from app.models.portfolio_account import PortfolioAccount
from app.models.position import Position
from app.repositories.portfolio import PortfolioRepository
from app.schemas.portfolio import PortfolioSummaryRead, PositionRead

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
