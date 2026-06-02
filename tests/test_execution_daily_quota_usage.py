from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from app.models.execution_daily_quota_usage import ExecutionDailyQuotaUsage
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_daily_quota_usage import ExecutionDailyQuotaUsageRepository
from app.repositories.paper_accounting import PaperAccountingRepository
from app.repositories.portfolio import PortfolioRepository
from app.services.brokers.base import BrokerOrderIntent
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService
from app.services.execution_limits import ExecutionDailyLimitService
from app.services.execution_safety_status import ExecutionSafetyStatusService
from app.services.paper_portfolio import PaperPortfolioService
from app.services.portfolio import PortfolioService
from app.services.portfolio_account import PortfolioAccountService
from app.services.simulated_execution import PaperExecutionBroker, PaperExecutionService
from app.core.config import Settings


DAY_ONE = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
DAY_TWO = datetime(2026, 6, 3, 1, 0, tzinfo=timezone.utc)


def build_broker(
    session,
    market_data_service,
    *,
    max_daily_order_count: int | None = None,
    now=DAY_ONE,
) -> PaperExecutionBroker:
    repository = PortfolioRepository(session)
    PortfolioAccountService(repository).ensure_account(base_currency="USD", starting_cash=Decimal("1000.00"))
    limit_service = ExecutionDailyLimitService(
        ExecutionAttemptRepository(session),
        paper_accounting_repository=PaperAccountingRepository(session),
        now_provider=lambda: now,
    )
    service = PaperExecutionService(
        repository=repository,
        market_data_service=market_data_service,
        simulation_enabled=True,
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        safety_guard=ExecutionSafetyGuard(
            ExecutionSafetyConfig(max_daily_order_count=max_daily_order_count),
            daily_limit_service=limit_service,
        ),
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(session)),
    )
    return PaperExecutionBroker(
        service,
        safety_guard=service.safety_guard,
        attempt_service=ExecutionAttemptService(ExecutionAttemptRepository(session)),
    )


def quota_count(session, *, bot_id: int | None, day=DAY_ONE.date()) -> int:
    usage = (
        session.query(ExecutionDailyQuotaUsage)
        .filter(ExecutionDailyQuotaUsage.bot_id == bot_id, ExecutionDailyQuotaUsage.utc_day == day)
        .one_or_none()
    )
    return usage.accepted_order_count if usage is not None else 0


def test_first_accepted_paper_execution_creates_and_increments_quota_usage(
    db_session,
    stub_market_data_service,
) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=2)
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is True
    assert quota_count(db_session, bot_id=1) == 1


def test_multiple_accepted_executions_increment_durable_count(db_session, stub_market_data_service) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=3)
    stub_market_data_service.set_price("BTCUSDT", "100")

    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("2")))
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    assert quota_count(db_session, bot_id=1) == 2


def test_quota_exhaustion_blocks_next_execution_without_accepted_state(db_session, stub_market_data_service) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=1)
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")

    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is False
    assert result.reason == "max_daily_order_count_exceeded"
    assert quota_count(db_session, bot_id=1) == 1
    assert len(repository.list_fills()) == 1
    assert len(PaperAccountingRepository(db_session).list_events()) == 1


def test_blocked_execution_does_not_increment_quota(db_session, stub_market_data_service) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=2)
    broker.safety_guard.config = ExecutionSafetyConfig(global_enabled=False, max_daily_order_count=2)
    broker.execution_service.safety_guard = broker.safety_guard
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert result.accepted is False
    assert result.reason == "execution_global_disabled"
    assert quota_count(db_session, bot_id=1) == 0
    assert PortfolioRepository(db_session).list_orders() == []
    assert PortfolioRepository(db_session).list_fills() == []
    assert PaperAccountingRepository(db_session).list_events() == []


@pytest.mark.parametrize(
    ("intent", "expected_reason"),
    [
        (BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("0")), "invalid_order_quantity"),
        (BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("100")), "insufficient_paper_cash"),
        (
            BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")),
            "Insufficient position quantity for this sell order",
        ),
    ],
)
def test_rejected_executions_do_not_increment_quota(
    db_session,
    stub_market_data_service,
    intent,
    expected_reason,
) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=2)
    stub_market_data_service.set_price("BTCUSDT", "100")

    result = broker.submit_market_order(intent)

    assert result.accepted is False
    assert result.reason == expected_reason
    assert quota_count(db_session, bot_id=1) == 0


def test_transaction_rollback_does_not_consume_quota_or_leave_partial_state(
    db_session,
    stub_market_data_service,
    monkeypatch,
) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=2)
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")

    def fail_after_accounting(*args, **kwargs):
        raise RuntimeError("boom after accounting")

    monkeypatch.setattr(PaperExecutionService, "_finalize_attempt", fail_after_accounting)

    with pytest.raises(RuntimeError, match="boom after accounting"):
        broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert quota_count(db_session, bot_id=1) == 0
    assert repository.list_orders() == []
    assert repository.list_fills() == []
    assert PaperAccountingRepository(db_session).list_events() == []
    assert ExecutionAttemptRepository(db_session).list_filtered() == []


def test_two_bots_have_independent_quotas(db_session, stub_market_data_service) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=1)
    stub_market_data_service.set_price("BTCUSDT", "100")

    first = broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    second = broker.submit_market_order(BrokerOrderIntent(bot_id=2, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))

    assert first.accepted is True
    assert second.accepted is True
    assert quota_count(db_session, bot_id=1) == 1
    assert quota_count(db_session, bot_id=2) == 1


def test_next_utc_day_gets_separate_quota_row(db_session) -> None:
    service = ExecutionDailyLimitService(ExecutionAttemptRepository(db_session), now_provider=lambda: DAY_ONE)
    next_day_service = ExecutionDailyLimitService(ExecutionAttemptRepository(db_session), now_provider=lambda: DAY_TWO)

    service.reserve_accepted_order_quota(bot_id=1, max_daily_order_count=5, enforce_limit=True)
    next_day_service.reserve_accepted_order_quota(bot_id=1, max_daily_order_count=5, enforce_limit=True)

    assert quota_count(db_session, bot_id=1, day=DAY_ONE.date()) == 1
    assert quota_count(db_session, bot_id=1, day=DAY_TWO.date()) == 1


def test_paper_portfolio_reset_does_not_clear_daily_quota_usage(db_session, stub_market_data_service) -> None:
    broker = build_broker(db_session, stub_market_data_service, max_daily_order_count=2)
    repository = PortfolioRepository(db_session)
    stub_market_data_service.set_price("BTCUSDT", "100")
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="buy", quantity=Decimal("1")))
    broker.submit_market_order(BrokerOrderIntent(bot_id=1, symbol="BTCUSDT", side="sell", quantity=Decimal("1")))

    PortfolioService(repository, stub_market_data_service).reset_paper_portfolio(Decimal("1000"))

    assert quota_count(db_session, bot_id=1) == 2


def test_safety_status_reads_durable_count_and_remaining_capacity(db_session) -> None:
    db_session.add(ExecutionDailyQuotaUsage(bot_id=1, utc_day=DAY_ONE.date(), accepted_order_count=2))
    db_session.commit()
    service = ExecutionSafetyStatusService(
        ExecutionAttemptRepository(db_session),
        Settings(EXECUTION_MAX_DAILY_ORDER_COUNT=3),
        now_provider=lambda: DAY_ONE,
    )

    status = service.get_status(bot_id=1)

    assert status.current_daily_attempt_count == 2
    assert status.remaining_daily_order_capacity == 1


def test_postgresql_path_uses_conflict_safe_initialization_and_row_locking() -> None:
    class FakeBind:
        dialect = postgresql.dialect()

    class FakeSession:
        bind = FakeBind()

        def __init__(self):
            self.executed_sql = ""
            self.scalar_sql = ""

        def execute(self, statement):
            self.executed_sql = str(statement.compile(dialect=postgresql.dialect()))

        def flush(self):
            return None

        def scalar(self, statement):
            self.scalar_sql = str(statement.compile(dialect=postgresql.dialect()))
            return None

    session = FakeSession()
    repository = ExecutionDailyQuotaUsageRepository(session)  # type: ignore[arg-type]

    repository.ensure_for_day(bot_id=1, utc_day=DAY_ONE.date())
    repository.get_for_day_for_update(bot_id=1, utc_day=DAY_ONE.date())

    assert "ON CONFLICT (bot_id, utc_day) DO NOTHING" in session.executed_sql
    assert "FOR UPDATE" in session.scalar_sql
