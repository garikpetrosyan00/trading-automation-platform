from decimal import Decimal

from app.core.errors import AppError
from app.models.paper_position import PaperPosition
from app.repositories.paper_position import PaperPositionRepository

ZERO = Decimal("0")


class PaperPositionService:
    def __init__(
        self,
        repository: PaperPositionRepository,
        *,
        autocommit: bool = True,
    ):
        self.repository = repository
        self.autocommit = autocommit

    def get_current_position(self, *, bot_id: int, symbol: str) -> PaperPosition | None:
        return self.repository.get_for_bot_symbol(
            bot_id=bot_id,
            symbol=self._normalize_symbol(symbol),
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
