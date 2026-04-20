from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PortfolioAccount(Base):
    __tablename__ = "portfolio_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
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
