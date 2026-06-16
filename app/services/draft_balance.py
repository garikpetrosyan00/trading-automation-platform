from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import NotFoundError
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

    def _ensure_bot_exists(self, bot_id: int) -> None:
        if self.bot_repository.get_by_id(bot_id) is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

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
