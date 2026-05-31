from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.brokers.base import BrokerOrderIntent
from app.services.execution_limits import ExecutionDailyLimitService

ZERO = Decimal("0")


@dataclass(frozen=True)
class ExecutionSafetyConfig:
    global_enabled: bool = True
    live_enabled: bool = False
    testnet_order_submission_enabled: bool = False
    max_order_notional: Decimal | None = None
    max_daily_order_count: int | None = None
    max_daily_loss: Decimal | None = None


@dataclass(frozen=True)
class ExecutionSafetyDecision:
    allowed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionSafetyGuard:
    def __init__(
        self,
        config: ExecutionSafetyConfig | None = None,
        daily_limit_service: ExecutionDailyLimitService | None = None,
    ):
        self.config = config or ExecutionSafetyConfig()
        self.daily_limit_service = daily_limit_service

    def validate_order(
        self,
        intent: BrokerOrderIntent,
        *,
        broker: str,
        market_price: Decimal | None = None,
    ) -> ExecutionSafetyDecision:
        metadata = {
            "broker": broker,
            "mode": intent.mode,
            "symbol": intent.symbol.strip().upper() if intent.symbol else intent.symbol,
            "side": intent.side,
        }

        if not self.config.global_enabled:
            return self._blocked("execution_global_disabled", metadata)

        if intent.mode not in {"paper", "testnet", "live"}:
            return self._blocked("unsupported_execution_mode", metadata)

        if intent.mode == "live" and not self.config.live_enabled:
            return self._blocked("live_execution_disabled", metadata)

        if intent.mode == "testnet" and not self.config.testnet_order_submission_enabled:
            return self._blocked("testnet_order_submission_disabled", metadata)

        if not intent.quantity.is_finite() or intent.quantity <= ZERO:
            return self._blocked("invalid_order_quantity", metadata)

        if market_price is not None:
            if not market_price.is_finite() or market_price <= ZERO:
                return self._blocked("invalid_market_price", {**metadata, "market_price": str(market_price)})
            notional = intent.quantity * market_price
            if self.config.max_order_notional is not None and notional > self.config.max_order_notional:
                return self._blocked(
                    "max_order_notional_exceeded",
                    {
                        **metadata,
                        "notional": str(notional),
                        "max_order_notional": str(self.config.max_order_notional),
                    },
                )

        if self.config.max_daily_order_count is not None and self.config.max_daily_order_count > 0:
            if self.daily_limit_service is None:
                return self._blocked("daily_limit_service_unavailable", metadata)
            snapshot = self.daily_limit_service.count_successful_orders_today(bot_id=intent.bot_id)
            if snapshot.count >= self.config.max_daily_order_count:
                return self._blocked(
                    "max_daily_order_count_exceeded",
                    {
                        **metadata,
                        "bot_id": intent.bot_id,
                        "daily_order_count": snapshot.count,
                        "max_daily_order_count": self.config.max_daily_order_count,
                        "day_start": snapshot.day_start.isoformat(),
                    },
                )

        if (
            intent.mode == "paper"
            and intent.side == "buy"
            and self.config.max_daily_loss is not None
            and self.config.max_daily_loss > ZERO
        ):
            if self.daily_limit_service is None:
                return self._blocked("daily_limit_service_unavailable", metadata)
            daily_loss = self.daily_limit_service.get_realized_loss_today()
            if daily_loss.realized_loss >= self.config.max_daily_loss:
                return self._blocked(
                    "max_daily_loss_exceeded",
                    {
                        **metadata,
                        "current_daily_realized_pnl": str(daily_loss.realized_pnl),
                        "current_daily_realized_loss": str(daily_loss.realized_loss),
                        "max_daily_loss": str(self.config.max_daily_loss),
                        "remaining_daily_loss_capacity": "0",
                        "day_start": daily_loss.day_start.isoformat(),
                    },
                )

        return ExecutionSafetyDecision(allowed=True, reason="allowed", metadata=metadata)

    @staticmethod
    def _blocked(reason: str, metadata: dict[str, Any]) -> ExecutionSafetyDecision:
        return ExecutionSafetyDecision(allowed=False, reason=reason, metadata=metadata)
