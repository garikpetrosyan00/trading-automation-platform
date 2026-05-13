from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

ZERO = Decimal("0")
HUNDRED = Decimal("100")

RISK_REASON_ALLOWED = "allowed"
RISK_REASON_MAX_TRADE_QUANTITY_EXCEEDED = "max_trade_quantity_exceeded"
RISK_REASON_MAX_POSITION_QUANTITY_EXCEEDED = "max_position_quantity_exceeded"
RISK_REASON_STOP_LOSS_TRIGGERED = "stop_loss_triggered"


@dataclass(frozen=True)
class RiskLimits:
    max_trade_quantity: Decimal | None = None
    max_position_quantity: Decimal | None = None
    stop_loss_percent: Decimal | None = None

    @classmethod
    def from_profile(cls, profile) -> "RiskLimits":
        if profile is None:
            return cls()
        return cls(
            max_trade_quantity=getattr(profile, "max_trade_quantity", None),
            max_position_quantity=getattr(profile, "max_position_quantity", None),
            stop_loss_percent=getattr(profile, "stop_loss_percent", None),
        )


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    action: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def evaluate(
        self,
        *,
        action: str,
        quantity: Decimal | None = None,
        current_position_quantity: Decimal = ZERO,
        entry_price: Decimal | None = None,
        current_price: Decimal | None = None,
    ) -> RiskDecision:
        stop_loss_decision = self._evaluate_stop_loss(
            current_position_quantity=current_position_quantity,
            entry_price=entry_price,
            current_price=current_price,
        )
        if stop_loss_decision is not None:
            return self._evaluate_trade_limits(
                stop_loss_decision.action,
                current_position_quantity,
                current_position_quantity,
                stop_loss_decision,
            )

        decision = RiskDecision(
            allowed=True,
            action=action,
            reason=RISK_REASON_ALLOWED,
            details={"current_position_quantity": str(current_position_quantity)},
        )
        return self._evaluate_trade_limits(action, quantity, current_position_quantity, decision)

    def _evaluate_trade_limits(
        self,
        action: str,
        quantity: Decimal | None,
        current_position_quantity: Decimal,
        allowed_decision: RiskDecision,
    ) -> RiskDecision:
        if action not in {"buy", "sell"} or quantity is None:
            return allowed_decision

        if self.limits.max_trade_quantity is not None and quantity > self.limits.max_trade_quantity:
            return RiskDecision(
                allowed=False,
                action="skip",
                reason=RISK_REASON_MAX_TRADE_QUANTITY_EXCEEDED,
                details={
                    "action": action,
                    "quantity": str(quantity),
                    "max_trade_quantity": str(self.limits.max_trade_quantity),
                },
            )

        if (
            action == "buy"
            and self.limits.max_position_quantity is not None
        ):
            requested_position_quantity = current_position_quantity + quantity
            if requested_position_quantity > self.limits.max_position_quantity:
                return RiskDecision(
                    allowed=False,
                    action="skip",
                    reason=RISK_REASON_MAX_POSITION_QUANTITY_EXCEEDED,
                    details={
                        "quantity": str(quantity),
                        "current_position_quantity": str(current_position_quantity),
                        "requested_position_quantity": str(requested_position_quantity),
                        "max_position_quantity": str(self.limits.max_position_quantity),
                    },
                )

        return allowed_decision

    def _evaluate_stop_loss(
        self,
        *,
        current_position_quantity: Decimal,
        entry_price: Decimal | None,
        current_price: Decimal | None,
    ) -> RiskDecision | None:
        if (
            self.limits.stop_loss_percent is None
            or current_position_quantity <= ZERO
            or entry_price is None
            or current_price is None
        ):
            return None

        stop_price = entry_price * (HUNDRED - self.limits.stop_loss_percent) / HUNDRED
        if current_price <= stop_price:
            return RiskDecision(
                allowed=True,
                action="sell",
                reason=RISK_REASON_STOP_LOSS_TRIGGERED,
                details={
                    "current_position_quantity": str(current_position_quantity),
                    "entry_price": str(entry_price),
                    "current_price": str(current_price),
                    "stop_price": str(stop_price),
                    "stop_loss_percent": str(self.limits.stop_loss_percent),
                },
            )

        return None
