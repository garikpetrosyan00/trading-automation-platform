from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.brokers.base import BrokerOrderIntent

ZERO = Decimal("0")


@dataclass(frozen=True)
class ExecutionSafetyConfig:
    global_enabled: bool = True
    live_enabled: bool = False
    testnet_order_submission_enabled: bool = False
    max_order_notional: Decimal | None = None


@dataclass(frozen=True)
class ExecutionSafetyDecision:
    allowed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionSafetyGuard:
    def __init__(self, config: ExecutionSafetyConfig | None = None):
        self.config = config or ExecutionSafetyConfig()

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

        return ExecutionSafetyDecision(allowed=True, reason="allowed", metadata=metadata)

    @staticmethod
    def _blocked(reason: str, metadata: dict[str, Any]) -> ExecutionSafetyDecision:
        return ExecutionSafetyDecision(allowed=False, reason=reason, metadata=metadata)
