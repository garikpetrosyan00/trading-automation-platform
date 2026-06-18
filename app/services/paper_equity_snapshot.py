from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.errors import NotFoundError
from app.data.schemas import MarketEvent
from app.models.paper_equity_snapshot import PaperEquitySnapshot
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_equity_snapshot import PaperEquitySnapshotRepository
from app.repositories.paper_position import PaperPositionRepository

ZERO = Decimal("0")


@dataclass(frozen=True)
class PaperEquitySnapshotList:
    bot_id: int
    items: list[PaperEquitySnapshot]


@dataclass(frozen=True)
class PaperEquitySnapshotPublicItem:
    id: int
    bot_id: int
    symbol: str
    quote_asset: str
    cash_available: Decimal
    cash_locked: Decimal
    base_quantity: Decimal
    base_locked: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    market_price: Decimal | None
    position_value: Decimal | None
    total_equity: Decimal | None
    event_type: str
    created_at: datetime


class PaperEquitySnapshotService:
    def __init__(
        self,
        repository: PaperEquitySnapshotRepository,
        draft_balance_repository: DraftBalanceRepository,
        paper_position_repository: PaperPositionRepository,
        market_data_service=None,
        *,
        bot_repository: BotRepository | None = None,
    ):
        self.repository = repository
        self.draft_balance_repository = draft_balance_repository
        self.paper_position_repository = paper_position_repository
        self.bot_repository = bot_repository
        self.market_data_service = market_data_service

    def list_bot_snapshots(
        self,
        bot_id: int,
        *,
        limit: int = 50,
    ) -> PaperEquitySnapshotList:
        if self.bot_repository is None:
            raise ValueError("bot_repository is required to read bot paper equity snapshots")
        bot = self.bot_repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        items = self.repository.list_latest_for_bot(bot_id=bot_id, limit=limit)
        return PaperEquitySnapshotList(
            bot_id=bot_id,
            items=[
                PaperEquitySnapshotPublicItem(
                    id=item.id,
                    bot_id=item.bot_id,
                    symbol=item.symbol,
                    quote_asset=item.quote_asset,
                    cash_available=item.cash_available,
                    cash_locked=item.cash_locked,
                    base_quantity=item.base_quantity,
                    base_locked=item.base_locked,
                    average_entry_price=item.average_entry_price,
                    realized_pnl=item.realized_pnl,
                    market_price=item.market_price,
                    position_value=item.position_value,
                    total_equity=item.total_equity,
                    event_type=item.event_type,
                    created_at=item.created_at,
                )
                for item in items
            ],
        )

    def create_snapshot(
        self,
        *,
        bot_id: int,
        symbol: str,
        base_asset: str,
        quote_asset: str,
        event_type: str,
        source_order_id: int | None = None,
        source_fill_id: int | None = None,
    ) -> PaperEquitySnapshot:
        normalized_symbol = self._normalize_identifier(symbol, "symbol")
        normalized_base_asset = self._normalize_identifier(base_asset, "base_asset")
        normalized_quote_asset = self._normalize_identifier(quote_asset, "quote_asset")

        quote_balance = self.draft_balance_repository.get_for_bot_asset(
            bot_id=bot_id,
            asset=normalized_quote_asset,
        )
        if quote_balance is None:
            raise NotFoundError(
                f"Draft balance asset {normalized_quote_asset} for bot {bot_id} was not found",
                error_code="draft_balance_asset_not_found",
            )
        base_balance = self.draft_balance_repository.get_for_bot_asset(
            bot_id=bot_id,
            asset=normalized_base_asset,
        )
        position = self.paper_position_repository.get_for_bot_symbol(
            bot_id=bot_id,
            symbol=normalized_symbol,
        )

        base_quantity = base_balance.available if base_balance is not None else ZERO
        base_locked = base_balance.locked if base_balance is not None else ZERO
        average_entry_price = position.average_entry_price if position is not None else ZERO
        realized_pnl = position.realized_pnl if position is not None else ZERO
        market_price = self._get_local_market_price(normalized_symbol)
        total_base_quantity = base_quantity + base_locked
        position_value = total_base_quantity * market_price if market_price is not None else None
        cash_total = quote_balance.available + quote_balance.locked
        total_equity = (
            cash_total + position_value
            if position_value is not None
            else cash_total if total_base_quantity == ZERO else None
        )

        return self.repository.create(
            PaperEquitySnapshot(
                bot_id=bot_id,
                symbol=normalized_symbol,
                quote_asset=normalized_quote_asset,
                cash_available=quote_balance.available,
                cash_locked=quote_balance.locked,
                base_quantity=base_quantity,
                base_locked=base_locked,
                average_entry_price=average_entry_price,
                realized_pnl=realized_pnl,
                market_price=market_price,
                position_value=position_value,
                total_equity=total_equity,
                event_type=event_type,
                source_order_id=source_order_id,
                source_fill_id=source_fill_id,
            )
        )

    @staticmethod
    def _normalize_identifier(value: str, field: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError(f"{field} must not be blank")
        return normalized

    def _get_local_market_price(self, symbol: str) -> Decimal | None:
        if self.market_data_service is None:
            return None
        latest = self.market_data_service.get_latest(symbol)
        if latest is None or not isinstance(latest, MarketEvent):
            return None
        price = latest.price or latest.close
        if price is None or not price.is_finite() or price <= ZERO:
            return None
        return price
