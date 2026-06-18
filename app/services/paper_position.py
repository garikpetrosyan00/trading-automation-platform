from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.errors import AppError, NotFoundError
from app.data.schemas import MarketEvent
from app.models.paper_position import PaperPosition
from app.repositories.bot import BotRepository
from app.repositories.paper_position import PaperPositionRepository

ZERO = Decimal("0")
QUOTE_ASSET_SUFFIXES = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH")


@dataclass(frozen=True)
class PaperPositionSnapshot:
    bot_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    market_price: Decimal | None
    unrealized_pnl: Decimal | None
    position_value: Decimal | None
    updated_at: datetime | None


class PaperPositionService:
    def __init__(
        self,
        repository: PaperPositionRepository,
        *,
        autocommit: bool = True,
        bot_repository: BotRepository | None = None,
        market_data_service=None,
    ):
        self.repository = repository
        self.autocommit = autocommit
        self.bot_repository = bot_repository
        self.market_data_service = market_data_service

    def get_current_position(self, *, bot_id: int, symbol: str) -> PaperPosition | None:
        return self.repository.get_for_bot_symbol(
            bot_id=bot_id,
            symbol=self._normalize_symbol(symbol),
        )

    def get_bot_position_snapshot(self, bot_id: int) -> PaperPositionSnapshot:
        if self.bot_repository is None:
            raise ValueError("bot_repository is required to read a bot paper position")
        bot = self.bot_repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        symbol = self._normalize_symbol(bot.strategy.symbol)
        base_asset, quote_asset = self._symbol_assets(symbol)
        position = self.get_current_position(bot_id=bot_id, symbol=symbol)
        market_price = self._get_local_market_price(symbol)

        quantity = position.quantity if position is not None else ZERO
        average_entry_price = position.average_entry_price if position is not None else ZERO
        realized_pnl = position.realized_pnl if position is not None else ZERO
        position_value = quantity * market_price if market_price is not None else None
        unrealized_pnl = (
            (market_price - average_entry_price) * quantity
            if market_price is not None
            else None
        )

        return PaperPositionSnapshot(
            bot_id=bot_id,
            symbol=symbol,
            base_asset=position.base_asset if position is not None else base_asset,
            quote_asset=position.quote_asset if position is not None else quote_asset,
            quantity=quantity,
            average_entry_price=average_entry_price,
            realized_pnl=realized_pnl,
            market_price=market_price,
            unrealized_pnl=unrealized_pnl,
            position_value=position_value,
            updated_at=position.updated_at if position is not None else None,
        )

    def apply_buy_fill(
        self,
        *,
        bot_id: int,
        symbol: str,
        base_asset: str,
        quote_asset: str,
        quantity: Decimal,
        fill_price: Decimal,
        fee: Decimal = ZERO,
    ) -> PaperPosition:
        normalized_symbol, normalized_base_asset, normalized_quote_asset = self._normalize_identifiers(
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
        )
        self._validate_fill(quantity=quantity, fill_price=fill_price, fee=fee)

        position = self.repository.get_or_create_for_bot_symbol_for_update(
            bot_id=bot_id,
            symbol=normalized_symbol,
            base_asset=normalized_base_asset,
            quote_asset=normalized_quote_asset,
        )
        self._validate_assets(
            position,
            base_asset=normalized_base_asset,
            quote_asset=normalized_quote_asset,
        )

        existing_cost_basis = position.quantity * position.average_entry_price
        new_quantity = position.quantity + quantity
        new_cost_basis = existing_cost_basis + (quantity * fill_price) + fee

        position.quantity = new_quantity
        position.average_entry_price = new_cost_basis / new_quantity
        self._commit_if_enabled(position)
        return position

    def apply_sell_fill(
        self,
        *,
        bot_id: int,
        symbol: str,
        base_asset: str,
        quote_asset: str,
        quantity: Decimal,
        fill_price: Decimal,
        fee: Decimal = ZERO,
    ) -> PaperPosition:
        normalized_symbol, normalized_base_asset, normalized_quote_asset = self._normalize_identifiers(
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
        )
        self._validate_fill(quantity=quantity, fill_price=fill_price, fee=fee)

        position = self.repository.get_for_bot_symbol_for_update(
            bot_id=bot_id,
            symbol=normalized_symbol,
        )
        if position is None or position.quantity < quantity:
            raise AppError(
                "Insufficient paper position quantity",
                status_code=409,
                error_code="insufficient_paper_position_quantity",
            )
        self._validate_assets(
            position,
            base_asset=normalized_base_asset,
            quote_asset=normalized_quote_asset,
        )

        proceeds = (quantity * fill_price) - fee
        realized_pnl_delta = proceeds - (quantity * position.average_entry_price)
        position.quantity -= quantity
        position.realized_pnl += realized_pnl_delta
        if position.quantity == ZERO:
            position.average_entry_price = ZERO

        self._commit_if_enabled(position)
        return position

    def _commit_if_enabled(self, position: PaperPosition) -> None:
        if self.autocommit:
            self.repository.commit()
            self.repository.refresh(position)

    @classmethod
    def _normalize_identifiers(
        cls,
        *,
        symbol: str,
        base_asset: str,
        quote_asset: str,
    ) -> tuple[str, str, str]:
        return (
            cls._normalize_symbol(symbol),
            cls._normalize_asset(base_asset),
            cls._normalize_asset(quote_asset),
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized

    @staticmethod
    def _normalize_asset(asset: str) -> str:
        normalized = asset.strip().upper()
        if not normalized:
            raise ValueError("asset must not be blank")
        return normalized

    @staticmethod
    def _validate_fill(*, quantity: Decimal, fill_price: Decimal, fee: Decimal) -> None:
        if not quantity.is_finite() or quantity <= ZERO:
            raise AppError(
                "Paper position fill quantity must be positive",
                status_code=422,
                error_code="invalid_paper_position_fill",
            )
        if not fill_price.is_finite() or fill_price <= ZERO:
            raise AppError(
                "Paper position fill price must be positive",
                status_code=422,
                error_code="invalid_paper_position_fill",
            )
        if not fee.is_finite() or fee < ZERO:
            raise AppError(
                "Paper position fill fee must not be negative",
                status_code=422,
                error_code="invalid_paper_position_fill",
            )

    @staticmethod
    def _validate_assets(
        position: PaperPosition,
        *,
        base_asset: str,
        quote_asset: str,
    ) -> None:
        if position.base_asset != base_asset or position.quote_asset != quote_asset:
            raise AppError(
                "Paper position asset mapping does not match",
                status_code=409,
                error_code="paper_position_asset_mismatch",
            )

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

    @staticmethod
    def _symbol_assets(symbol: str) -> tuple[str, str]:
        for quote_asset in QUOTE_ASSET_SUFFIXES:
            if symbol.endswith(quote_asset) and len(symbol) > len(quote_asset):
                return symbol[: -len(quote_asset)], quote_asset
        return symbol, "USDT"
