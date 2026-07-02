from __future__ import annotations

from decimal import Decimal

from app.core.errors import AppError, NotFoundError
from app.models.bot import Bot
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository
from app.repositories.paper_position import PaperPositionRepository

ZERO = Decimal("0")


class PaperSafetyGateService:
    """Read-only validation for bot-scoped paper execution preconditions."""

    def __init__(
        self,
        *,
        bot_repository: BotRepository,
        draft_balance_repository: DraftBalanceRepository,
        paper_position_repository: PaperPositionRepository,
    ):
        self.bot_repository = bot_repository
        self.draft_balance_repository = draft_balance_repository
        self.paper_position_repository = paper_position_repository

    def validate_bot_paper_execution_allowed(
        self,
        *,
        bot_id: int,
        require_runnable: bool = True,
    ) -> Bot:
        bot = self.bot_repository.get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        execution_mode = bot.execution_mode or ("paper" if bot.is_paper else "live")
        if execution_mode != "paper" or not bot.is_paper:
            raise AppError(
                "Paper execution requires a paper-mode bot",
                status_code=409,
                error_code="paper_execution_mode_required",
            )
        if require_runnable and bot.status != "active":
            raise AppError(
                "Bot is not active and runnable",
                status_code=409,
                error_code="bot_not_runnable",
            )
        return bot

    def validate_paper_buy_allowed(
        self,
        *,
        bot_id: int,
        quote_asset: str,
        required_quote_amount: Decimal,
        require_runnable: bool = True,
    ) -> None:
        self.validate_bot_paper_execution_allowed(bot_id=bot_id, require_runnable=require_runnable)
        self._validate_positive_amount(required_quote_amount)

        normalized_quote_asset = self._normalize_asset(quote_asset)
        row = self.draft_balance_repository.get_for_bot_asset(
            bot_id=bot_id,
            asset=normalized_quote_asset,
        )
        if row is None:
            raise NotFoundError(
                f"Draft balance asset {normalized_quote_asset} for bot {bot_id} was not found",
                error_code="draft_balance_asset_not_found",
            )
        if row.available < required_quote_amount:
            raise AppError(
                "Insufficient draft balance available amount",
                status_code=409,
                error_code="insufficient_draft_balance_available",
            )

    def validate_paper_sell_allowed(
        self,
        *,
        bot_id: int,
        symbol: str,
        base_asset: str,
        quote_asset: str,
        quantity: Decimal,
        require_runnable: bool = True,
    ) -> None:
        self.validate_bot_paper_execution_allowed(bot_id=bot_id, require_runnable=require_runnable)
        self._validate_positive_amount(quantity)

        normalized_symbol = self._normalize_symbol(symbol)
        normalized_base_asset = self._normalize_asset(base_asset)
        normalized_quote_asset = self._normalize_asset(quote_asset)
        position = self.paper_position_repository.get_for_bot_symbol(
            bot_id=bot_id,
            symbol=normalized_symbol,
        )
        if position is None or position.quantity < quantity:
            raise AppError(
                "Insufficient paper position quantity",
                status_code=409,
                error_code="insufficient_paper_position_quantity",
            )
        if position.base_asset != normalized_base_asset or position.quote_asset != normalized_quote_asset:
            raise AppError(
                "Paper position asset mapping does not match",
                status_code=409,
                error_code="paper_position_asset_mismatch",
            )
        row = self.draft_balance_repository.get_for_bot_asset(
            bot_id=bot_id,
            asset=normalized_base_asset,
        )
        if row is None:
            raise NotFoundError(
                f"Draft balance asset {normalized_base_asset} for bot {bot_id} was not found",
                error_code="draft_balance_asset_not_found",
            )
        if row.available < quantity:
            raise AppError(
                "Insufficient draft balance available amount",
                status_code=409,
                error_code="insufficient_draft_balance_available",
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
    def _validate_positive_amount(amount: Decimal) -> None:
        if not amount.is_finite() or amount <= ZERO:
            raise AppError(
                "Paper safety gate amount must be positive",
                status_code=422,
                error_code="invalid_paper_safety_gate_amount",
            )
