from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_execution_attempts_side"),
        CheckConstraint("mode IN ('paper', 'testnet', 'live')", name="ck_execution_attempts_mode"),
        CheckConstraint(
            "final_status IN ("
            "'created', "
            "'blocked_by_risk', "
            "'blocked_by_safety', "
            "'rejected_by_broker', "
            "'order_created', "
            "'filled', "
            "'failed'"
            ")",
            name="ck_execution_attempts_final_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    broker: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    safety_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    final_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    final_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
