from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class BrokerOrderIntent:
    symbol: str
    side: str
    quantity: Decimal
    bot_id: int | None = None
    strategy_id: int | None = None
    order_type: str = "market"
    mode: str = "paper"
    decision_reason: str | None = None
    decision_metadata: dict[str, Any] | None = None
    market_price: Decimal | None = None


@dataclass(frozen=True)
class BrokerOrderResult:
    accepted: bool
    status: str
    message: str
    order_id: int | None = None
    external_order_id: str | None = None
    executed_quantity: Decimal | None = None
    executed_price: Decimal | None = None
    fee: Decimal | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_response: Any | None = None


class ExecutionBroker(Protocol):
    def submit_market_order(self, intent: BrokerOrderIntent) -> BrokerOrderResult:
        """Submit a market order intent through a concrete execution broker."""
