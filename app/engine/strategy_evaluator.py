from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class StrategyDecision:
    action: str
    reason: str


class StrategyEvaluator:
    @staticmethod
    def evaluate_price_threshold(
        latest_price: Decimal | None,
        position_quantity: Decimal,
        entry_below: Decimal | None,
        exit_above: Decimal | None,
    ) -> StrategyDecision:
        if latest_price is None:
            return StrategyDecision(action="skip", reason="no_latest_price")

        if position_quantity <= Decimal("0"):
            if entry_below is None:
                return StrategyDecision(action="skip", reason="entry_below_not_configured")
            if latest_price <= entry_below:
                return StrategyDecision(action="buy", reason="entry_threshold_reached")
            return StrategyDecision(action="hold", reason="entry_threshold_not_met")

        if exit_above is None:
            return StrategyDecision(action="skip", reason="exit_above_not_configured")
        if latest_price >= exit_above:
            return StrategyDecision(action="sell", reason="exit_threshold_reached")
        return StrategyDecision(action="hold", reason="exit_threshold_not_met")
