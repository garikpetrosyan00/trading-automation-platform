from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SimulatedOrderSide = Literal["buy", "sell"]
SimulatedOrderStatus = Literal["created", "submitted", "filled", "rejected", "cancelled"]
ExecutionMode = Literal["paper", "live"]


class SimulatedOrder(Base):
    __tablename__ = "simulated_orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_simulated_orders_side"),
        CheckConstraint(
            "status IN ('created', 'submitted', 'filled', 'rejected', 'cancelled')",
            name="ck_simulated_orders_status",
        ),
        CheckConstraint("mode IN ('paper', 'live')", name="ck_simulated_orders_mode"),
        CheckConstraint("order_type IN ('market')", name="ck_simulated_orders_order_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False, default="market", server_default="market")
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    requested_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="paper", server_default="paper", index=True)
    decision_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
