from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.data.schemas import MarketEvent


class BaseMarketDataProvider(ABC):
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    async def connect(self) -> None:
        """Open any provider resources before streaming."""

    async def disconnect(self) -> None:
        """Close any provider resources after streaming."""

    @abstractmethod
    async def stream_events(self) -> AsyncIterator[MarketEvent]:
        raise NotImplementedError
