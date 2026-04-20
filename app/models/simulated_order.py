from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SimulatedOrderSide = Literal["buy", "sell"]
SimulatedOrderStatus = Literal["filled", "rejected"]


class SimulatedOrder(Base):
    __tablename__ = "simulated_orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_simulated_orders_side"),
        CheckConstraint("status IN ('filled', 'rejected')", name="ck_simulated_orders_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    requested_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
