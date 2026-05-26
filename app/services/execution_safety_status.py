from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.config import Settings
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.services.brokers.base import BrokerOrderIntent
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_limits import ExecutionDailyLimitService


@dataclass(frozen=True)
class ExecutionSafetyStatus:
    global_execution_enabled: bool
    live_execution_enabled: bool
    paper_execution_allowed: bool
    binance_testnet_broker_enabled: bool
    binance_testnet_order_submission_enabled: bool
    binance_testnet_credentials_configured: bool
    max_order_notional: Decimal | None
    max_daily_order_count: int | None
    max_daily_loss: Decimal | None
    utc_day_start: datetime
    current_daily_attempt_count: int
    remaining_daily_order_capacity: int | None
    is_execution_currently_allowed: bool
    blocking_reason: str | None
    metadata: dict


class ExecutionSafetyStatusService:
    def __init__(self, repository: ExecutionAttemptRepository, settings: Settings, now_provider=None):
        self.repository = repository
        self.settings = settings
        self.daily_limit_service = ExecutionDailyLimitService(repository, now_provider=now_provider)

    def get_status(
        self,
        *,
        bot_id: int | None = None,
        mode: str = "paper",
        broker: str = "paper",
        side: str = "buy",
        quantity: Decimal = Decimal("1"),
        market_price: Decimal | None = None,
    ) -> ExecutionSafetyStatus:
        config = self._build_safety_config()
        snapshot = self.daily_limit_service.count_successful_orders_today(bot_id=bot_id)
        guard = ExecutionSafetyGuard(config, daily_limit_service=self.daily_limit_service)
        decision = guard.validate_order(
            BrokerOrderIntent(
                bot_id=bot_id,
                symbol="BTCUSDT",
                side=side,
                quantity=quantity,
                mode=mode,
            ),
            broker=broker,
            market_price=market_price,
        )
        remaining_capacity = self._remaining_daily_order_capacity(config.max_daily_order_count, snapshot.count)

        return ExecutionSafetyStatus(
            global_execution_enabled=self.settings.execution_global_enabled,
            live_execution_enabled=self.settings.execution_live_enabled,
            paper_execution_allowed=self.settings.execution_global_enabled,
            binance_testnet_broker_enabled=self.settings.binance_testnet_broker_enabled,
            binance_testnet_order_submission_enabled=self.settings.binance_testnet_order_submission_enabled,
            binance_testnet_credentials_configured=bool(
                self.settings.binance_testnet_api_key and self.settings.binance_testnet_api_secret
            ),
            max_order_notional=self.settings.execution_max_order_notional,
            max_daily_order_count=self.settings.execution_max_daily_order_count,
            max_daily_loss=self.settings.execution_max_daily_loss,
            utc_day_start=snapshot.day_start,
            current_daily_attempt_count=snapshot.count,
            remaining_daily_order_capacity=remaining_capacity,
            is_execution_currently_allowed=decision.allowed,
            blocking_reason=None if decision.allowed else decision.reason,
            metadata=decision.metadata,
        )

    def _build_safety_config(self) -> ExecutionSafetyConfig:
        return ExecutionSafetyConfig(
            global_enabled=self.settings.execution_global_enabled,
            live_enabled=self.settings.execution_live_enabled,
            testnet_order_submission_enabled=self.settings.binance_testnet_order_submission_enabled,
            max_order_notional=self.settings.execution_max_order_notional,
            max_daily_order_count=self.settings.execution_max_daily_order_count,
            max_daily_loss=self.settings.execution_max_daily_loss,
        )

    @staticmethod
    def _remaining_daily_order_capacity(max_daily_order_count: int | None, current_count: int) -> int | None:
        if max_daily_order_count is None or max_daily_order_count <= 0:
            return None
        return max(max_daily_order_count - current_count, 0)
