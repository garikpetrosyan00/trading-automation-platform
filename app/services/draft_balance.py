from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import AppError, NotFoundError
from app.models.draft_balance import DraftBalance
from app.repositories.bot import BotRepository
from app.repositories.draft_balance import DraftBalanceRepository

ZERO = Decimal("0")
DEFAULT_DRAFT_BALANCE = {
    "USDT": (Decimal("10000"), ZERO),
    "BTC": (ZERO, ZERO),
}


@dataclass(frozen=True)
class DraftBalanceAsset:
    asset: str
    available: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.available + self.locked


@dataclass(frozen=True)
class DraftBalanceSnapshot:
    bot_id: int
    assets: list[DraftBalanceAsset]


class DraftBalanceService:
    def __init__(
        self,
        repository: DraftBalanceRepository,
        bot_repository: BotRepository,
    ):
        self.repository = repository
        self.bot_repository = bot_repository

    def get_bot_draft_balance(self, bot_id: int) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def reset_bot_draft_balance(
        self,
        bot_id: int,
        defaults: dict[str, tuple[Decimal, Decimal]] | None = None,
    ) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        for asset, amounts in (defaults or DEFAULT_DRAFT_BALANCE).items():
            normalized_asset = self._normalize_asset(asset)
            available, locked = amounts
            self._validate_amounts(available=available, locked=locked)
            self.repository.upsert_for_bot_asset(
                bot_id=bot_id,
                asset=normalized_asset,
                available=available,
                locked=locked,
            )
        self.repository.commit()
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def reserve_bot_draft_balance_asset(
        self,
        bot_id: int,
        asset: str,
        amount: Decimal,
    ) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        normalized_asset = self._normalize_asset(asset)
        self._validate_positive_amount(amount)
        row = self._get_required_asset_for_update(bot_id=bot_id, asset=normalized_asset)
        if row.available < amount:
            raise AppError(
                "Insufficient draft balance available amount",
                status_code=409,
                error_code="insufficient_draft_balance_available",
            )

        row.available -= amount
        row.locked += amount
        self._validate_row_non_negative(row)
        self.repository.commit()
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def release_bot_draft_balance_asset(
        self,
        bot_id: int,
        asset: str,
        amount: Decimal,
    ) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        normalized_asset = self._normalize_asset(asset)
        self._validate_positive_amount(amount)
        row = self._get_required_asset_for_update(bot_id=bot_id, asset=normalized_asset)
        if row.locked < amount:
            raise AppError(
                "Insufficient draft balance locked amount",
                status_code=409,
                error_code="insufficient_draft_balance_locked",
            )

        row.locked -= amount
        row.available += amount
        self._validate_row_non_negative(row)
        self.repository.commit()
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def apply_draft_balance_buy_fill(
        self,
        bot_id: int,
        base_asset: str,
        quote_asset: str,
        received_base_amount: Decimal,
        spent_quote_amount: Decimal,
    ) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        normalized_base_asset = self._normalize_asset(base_asset)
        normalized_quote_asset = self._normalize_asset(quote_asset)
        self._validate_positive_amount(received_base_amount)
        self._validate_positive_amount(spent_quote_amount)

        quote_row = self._get_required_asset_for_update(bot_id=bot_id, asset=normalized_quote_asset)
        if quote_row.locked < spent_quote_amount:
            raise AppError(
                "Insufficient draft balance locked amount",
                status_code=409,
                error_code="insufficient_draft_balance_locked",
            )
        base_row = self.repository.get_or_create_for_bot_asset_for_update(
            bot_id=bot_id,
            asset=normalized_base_asset,
        )

        quote_row.locked -= spent_quote_amount
        base_row.available += received_base_amount
        self._validate_row_non_negative(quote_row)
        self._validate_row_non_negative(base_row)
        self.repository.commit()
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def apply_draft_balance_sell_fill(
        self,
        bot_id: int,
        base_asset: str,
        quote_asset: str,
        sold_base_amount: Decimal,
        received_quote_amount: Decimal,
    ) -> DraftBalanceSnapshot:
        self._ensure_bot_exists(bot_id)
        normalized_base_asset = self._normalize_asset(base_asset)
        normalized_quote_asset = self._normalize_asset(quote_asset)
        self._validate_positive_amount(sold_base_amount)
        self._validate_positive_amount(received_quote_amount)

        base_row = self._get_required_asset_for_update(bot_id=bot_id, asset=normalized_base_asset)
        if base_row.locked < sold_base_amount:
            raise AppError(
                "Insufficient draft balance locked amount",
                status_code=409,
                error_code="insufficient_draft_balance_locked",
            )
        quote_row = self.repository.get_or_create_for_bot_asset_for_update(
            bot_id=bot_id,
            asset=normalized_quote_asset,
        )

        base_row.locked -= sold_base_amount
        quote_row.available += received_quote_amount
        self._validate_row_non_negative(base_row)
        self._validate_row_non_negative(quote_row)
        self.repository.commit()
        return DraftBalanceSnapshot(bot_id=bot_id, assets=self._build_assets(self.repository.list_for_bot(bot_id)))

    def _ensure_bot_exists(self, bot_id: int) -> None:
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

    def _get_required_asset_for_update(self, *, bot_id: int, asset: str) -> DraftBalance:
        row = self.repository.get_for_bot_asset_for_update(bot_id=bot_id, asset=asset)
        if row is None:
            raise NotFoundError(
                f"Draft balance asset {asset} for bot {bot_id} was not found",
                error_code="draft_balance_asset_not_found",
            )
        return row

    @classmethod
    def _build_assets(cls, rows: list[DraftBalance]) -> list[DraftBalanceAsset]:
        return [
            DraftBalanceAsset(
                asset=cls._normalize_asset(row.asset),
                available=row.available,
                locked=row.locked,
            )
            for row in rows
        ]

    @staticmethod
    def _normalize_asset(asset: str) -> str:
        normalized = asset.strip().upper()
        if not normalized:
            raise ValueError("asset must not be blank")
        return normalized

    @staticmethod
    def _validate_amounts(*, available: Decimal, locked: Decimal) -> None:
        if not available.is_finite() or available < ZERO:
            raise ValueError("available must be a non-negative finite decimal")
        if not locked.is_finite() or locked < ZERO:
            raise ValueError("locked must be a non-negative finite decimal")

    @staticmethod
    def _validate_positive_amount(amount: Decimal) -> None:
        if not amount.is_finite() or amount <= ZERO:
            raise AppError(
                "Draft balance amount must be a positive finite decimal",
                status_code=422,
                error_code="invalid_draft_balance_amount",
            )

    @staticmethod
    def _validate_row_non_negative(row: DraftBalance) -> None:
        if row.available < ZERO or row.locked < ZERO:
            raise AppError(
                "Draft balance amounts must not be negative",
                status_code=409,
                error_code="invalid_draft_balance_amount",
            )
