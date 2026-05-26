from __future__ import annotations

from dataclasses import dataclass

from app.services.brokers.base import BrokerOrderIntent, BrokerOrderResult


@dataclass(frozen=True)
class BinanceTestnetBrokerConfig:
    enabled: bool = False
    order_submission_enabled: bool = False
    base_url: str = "https://testnet.binance.vision"
    api_key: str | None = None
    api_secret: str | None = None


class BinanceTestnetBroker:
    def __init__(self, config: BinanceTestnetBrokerConfig, http_client=None):
        self.config = config
        self.http_client = http_client

    def submit_market_order(self, intent: BrokerOrderIntent) -> BrokerOrderResult:
        normalized_symbol = intent.symbol.strip().upper()
        if not normalized_symbol:
            return self._rejected("Symbol must not be empty", reason="invalid_symbol")
        if intent.side not in {"buy", "sell"}:
            return self._rejected("Order side must be buy or sell", reason="invalid_side")
        if intent.order_type != "market":
            return self._rejected("Only market orders are supported", reason="unsupported_order_type")
        if not intent.quantity.is_finite() or intent.quantity <= 0:
            return self._rejected("Order quantity must be a positive number", reason="invalid_quantity")

        if not self.config.enabled:
            return self._rejected(
                "Binance testnet broker is disabled",
                reason="testnet_broker_disabled",
                metadata={"base_url": self.config.base_url},
            )

        if not self.config.order_submission_enabled:
            return self._rejected(
                "Binance testnet order submission is disabled",
                reason="testnet_order_submission_disabled",
                metadata={"base_url": self.config.base_url},
            )

        if not self.config.api_key or not self.config.api_secret:
            return self._rejected(
                "Binance testnet API credentials are not configured",
                reason="missing_testnet_credentials",
                metadata={"base_url": self.config.base_url},
            )

        return self._rejected(
            "Binance testnet order submission is not implemented",
            reason="testnet_order_submission_not_implemented",
            metadata={"base_url": self.config.base_url},
        )

    @staticmethod
    def _rejected(
        message: str,
        *,
        reason: str,
        metadata: dict | None = None,
    ) -> BrokerOrderResult:
        return BrokerOrderResult(
            accepted=False,
            status="rejected",
            message=message,
            reason=reason,
            metadata=metadata or {},
        )
