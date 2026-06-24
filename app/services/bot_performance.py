from decimal import Decimal

from app.core.errors import NotFoundError
from app.models.run_event import RunEvent
from app.repositories.bot import BotRepository
from app.repositories.market_candle import MarketCandleRepository
from app.repositories.paper_position import PaperPositionRepository
from app.repositories.run_event import RunEventRepository
from app.repositories.strategy import StrategyRepository
from app.schemas.bot_performance import BotPerformanceRead

ZERO = Decimal("0")
RECENT_EVENT_LIMIT = 100


class BotPerformanceService:
    def __init__(self, db, market_data_service):
        self.db = db
        self.market_data_service = market_data_service

    def get_performance(self, bot_id: int) -> BotPerformanceRead:
        bot = BotRepository(self.db).get_by_id(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot with id {bot_id} was not found", error_code="bot_not_found")

        strategy = StrategyRepository(self.db).get_by_id(bot.strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy with id {bot.strategy_id} was not found", error_code="strategy_not_found")

        run_events = RunEventRepository(self.db).list_recent_for_bot(bot.id, limit=RECENT_EVENT_LIMIT)
        latest_event = run_events[0] if run_events else None
        latest_decision_event = next((event for event in run_events if self._decision_from_event(event) is not None), None)
        position = PaperPositionRepository(self.db).get_for_bot_symbol(
            bot_id=bot.id,
            symbol=strategy.symbol,
        )
        latest_price = self._latest_market_price(strategy.symbol, strategy.timeframe)

        current_position_quantity = position.quantity if position is not None else ZERO
        realized_pnl = position.realized_pnl if position is not None else None
        unrealized_pnl = None
        if position is not None and latest_price is not None and position.quantity > ZERO:
            unrealized_pnl = (latest_price - position.average_entry_price) * position.quantity

        decision_counts = {"buy": 0, "sell": 0, "hold": 0}
        for event in run_events:
            decision = self._decision_from_event(event)
            if decision in decision_counts:
                decision_counts[decision] += 1

        return BotPerformanceRead(
            bot_id=bot.id,
            name=bot.name,
            symbol=strategy.symbol,
            strategy_type=strategy.strategy_type,
            latest_market_price=latest_price,
            current_position_quantity=current_position_quantity,
            last_decision=self._decision_from_event(latest_decision_event) if latest_decision_event is not None else None,
            last_decision_reason=(
                self._decision_reason_from_event(latest_decision_event) if latest_decision_event is not None else None
            ),
            last_run_event_at=latest_event.created_at if latest_event is not None else None,
            recent_run_event_count=len(run_events),
            buy_decision_count=decision_counts["buy"],
            sell_decision_count=decision_counts["sell"],
            hold_decision_count=decision_counts["hold"],
            risk_blocked_event_count=sum(1 for event in run_events if self._is_risk_blocked_event(event)),
            filled_order_event_count=sum(1 for event in run_events if event.message == "order_filled"),
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            health=self._health(bot.status, run_events),
        )

    def _latest_market_price(self, symbol: str, timeframe: str) -> Decimal | None:
        latest = self.market_data_service.get_latest(symbol)
        if latest is not None:
            return latest.price or latest.close

        candles = MarketCandleRepository(self.db).list_recent(symbol=symbol, timeframe=timeframe, limit=1)
        if not candles:
            return None
        return candles[-1].close_price

    @staticmethod
    def _decision_from_event(event: RunEvent | None) -> str | None:
        if event is None:
            return None
        payload = event.payload or {}
        decision = payload.get("decision")
        if decision is None and event.message == "order_filled":
            decision = payload.get("side")
        if isinstance(decision, str):
            return decision.lower()
        return None

    @staticmethod
    def _decision_reason_from_event(event: RunEvent) -> str | None:
        payload = event.payload or {}
        reason = payload.get("detail") or payload.get("reason")
        return reason if isinstance(reason, str) else event.message

    @staticmethod
    def _is_risk_blocked_event(event: RunEvent) -> bool:
        payload = event.payload or {}
        return event.message == "risk_limit_blocked" or payload.get("reason") == "risk_limit_blocked"

    @staticmethod
    def _health(bot_status: str, run_events: list[RunEvent]) -> str:
        if not run_events:
            return "no_activity"
        if bot_status != "active":
            return "inactive"
        if run_events[0].level == "error":
            return "unknown"
        return "healthy"
