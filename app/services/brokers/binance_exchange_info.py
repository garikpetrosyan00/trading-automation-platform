from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

EXCHANGE_INFO_ENDPOINT = "/api/v3/exchangeInfo"
ZERO = Decimal("0")


@dataclass(frozen=True)
class BinanceQuantityFilter:
    filter_type: str
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal

    @property
    def meaningful(self) -> bool:
        return self.min_qty > ZERO or self.max_qty > ZERO or self.step_size > ZERO


@dataclass(frozen=True)
class BinanceMinNotionalFilter:
    min_notional: Decimal
    apply_to_market: bool


@dataclass(frozen=True)
class BinanceNotionalFilter:
    min_notional: Decimal
    max_notional: Decimal
    apply_min_to_market: bool
    apply_max_to_market: bool


@dataclass(frozen=True)
class BinanceSymbolRules:
    symbol: str
    status: str
    order_types: frozenset[str]
    lot_size: BinanceQuantityFilter | None = None
    market_lot_size: BinanceQuantityFilter | None = None
    min_notional: BinanceMinNotionalFilter | None = None
    notional: BinanceNotionalFilter | None = None


@dataclass(frozen=True)
class BinanceExchangeInfo:
    symbols: dict[str, BinanceSymbolRules]

    def get_symbol(self, symbol: str) -> BinanceSymbolRules | None:
        return self.symbols.get(symbol.strip().upper())


@dataclass(frozen=True)
class BinanceExchangeInfoHttpResponse:
    status_code: int
    payload: dict[str, Any] | None


class BinanceExchangeInfoError(Exception):
    pass


class BinanceExchangeInfoClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def fetch_exchange_info(self) -> BinanceExchangeInfo:
        response = self._fetch_raw_exchange_info()
        if response.status_code < 200 or response.status_code >= 300:
            raise BinanceExchangeInfoError("Binance testnet exchange info request failed")
        if response.payload is None:
            raise BinanceExchangeInfoError("Binance testnet exchange info response was invalid")
        return BinanceExchangeInfoParser.parse(response.payload)

    def _fetch_raw_exchange_info(self) -> BinanceExchangeInfoHttpResponse:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.get(EXCHANGE_INFO_ENDPOINT)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise BinanceExchangeInfoError("Could not reach Binance testnet exchange info endpoint") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceExchangeInfoError("Binance testnet exchange info response was invalid") from exc

        if not isinstance(payload, dict):
            raise BinanceExchangeInfoError("Binance testnet exchange info response was invalid")
        return BinanceExchangeInfoHttpResponse(status_code=response.status_code, payload=payload)


class BinanceExchangeInfoParser:
    @classmethod
    def parse(cls, payload: dict[str, Any]) -> BinanceExchangeInfo:
        symbols_payload = payload.get("symbols")
        if not isinstance(symbols_payload, list):
            raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")

        symbols: dict[str, BinanceSymbolRules] = {}
        for symbol_payload in symbols_payload:
            if not isinstance(symbol_payload, dict):
                raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")
            symbol = symbol_payload.get("symbol")
            status = symbol_payload.get("status")
            order_types = symbol_payload.get("orderTypes")
            filters = symbol_payload.get("filters")
            if not isinstance(symbol, str) or not isinstance(status, str):
                raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")
            if not isinstance(order_types, list) or not all(isinstance(value, str) for value in order_types):
                raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")
            if not isinstance(filters, list):
                raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")

            symbols[symbol.upper()] = BinanceSymbolRules(
                symbol=symbol.upper(),
                status=status,
                order_types=frozenset(order_types),
                lot_size=cls._quantity_filter(filters, "LOT_SIZE"),
                market_lot_size=cls._quantity_filter(filters, "MARKET_LOT_SIZE"),
                min_notional=cls._min_notional_filter(filters),
                notional=cls._notional_filter(filters),
            )
        return BinanceExchangeInfo(symbols=symbols)

    @classmethod
    def _quantity_filter(cls, filters: list[Any], filter_type: str) -> BinanceQuantityFilter | None:
        payload = cls._filter_payload(filters, filter_type)
        if payload is None:
            return None
        return BinanceQuantityFilter(
            filter_type=filter_type,
            min_qty=cls._decimal(payload.get("minQty")),
            max_qty=cls._decimal(payload.get("maxQty")),
            step_size=cls._decimal(payload.get("stepSize")),
        )

    @classmethod
    def _min_notional_filter(cls, filters: list[Any]) -> BinanceMinNotionalFilter | None:
        payload = cls._filter_payload(filters, "MIN_NOTIONAL")
        if payload is None:
            return None
        return BinanceMinNotionalFilter(
            min_notional=cls._decimal(payload.get("minNotional")),
            apply_to_market=bool(payload.get("applyToMarket")),
        )

    @classmethod
    def _notional_filter(cls, filters: list[Any]) -> BinanceNotionalFilter | None:
        payload = cls._filter_payload(filters, "NOTIONAL")
        if payload is None:
            return None
        return BinanceNotionalFilter(
            min_notional=cls._decimal(payload.get("minNotional")),
            max_notional=cls._decimal(payload.get("maxNotional")),
            apply_min_to_market=bool(payload.get("applyMinToMarket")),
            apply_max_to_market=bool(payload.get("applyMaxToMarket")),
        )

    @staticmethod
    def _filter_payload(filters: list[Any], filter_type: str) -> dict[str, Any] | None:
        for item in filters:
            if isinstance(item, dict) and item.get("filterType") == filter_type:
                return item
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed") from exc
        if not decimal_value.is_finite() or decimal_value < ZERO:
            raise BinanceExchangeInfoError("Binance testnet exchange info response was malformed")
        return decimal_value


class BinanceExchangeInfoProvider:
    def __init__(self, client: BinanceExchangeInfoClient, *, ttl_seconds: float = 300.0, monotonic_provider=None):
        self.client = client
        self.ttl_seconds = ttl_seconds
        self.monotonic_provider = monotonic_provider or time.monotonic
        self._cached_info: BinanceExchangeInfo | None = None
        self._expires_at: float = 0.0

    def get_exchange_info(self) -> BinanceExchangeInfo:
        now = self.monotonic_provider()
        if self._cached_info is not None and now < self._expires_at:
            return self._cached_info

        info = self.client.fetch_exchange_info()
        self._cached_info = info
        self._expires_at = now + self.ttl_seconds
        return info


@dataclass(frozen=True)
class BinanceOrderValidationDecision:
    allowed: bool
    reason: str
    metadata: dict[str, Any]


class BinanceMarketOrderValidator:
    def __init__(self, exchange_info_provider: BinanceExchangeInfoProvider):
        self.exchange_info_provider = exchange_info_provider

    def validate(self, *, symbol: str, quantity: Decimal, market_price: Decimal | None) -> BinanceOrderValidationDecision:
        normalized_symbol = symbol.strip().upper()
        try:
            exchange_info = self.exchange_info_provider.get_exchange_info()
        except BinanceExchangeInfoError:
            return self._rejected(
                "testnet_exchange_info_unavailable",
                {"symbol": normalized_symbol, "mode": "testnet", "broker": "binance_testnet"},
            )

        rules = exchange_info.get_symbol(normalized_symbol)
        if rules is None:
            return self._rejected("testnet_symbol_not_found", {"symbol": normalized_symbol})
        if rules.status != "TRADING":
            return self._rejected("testnet_symbol_not_trading", {"symbol": normalized_symbol, "status": rules.status})
        if "MARKET" not in rules.order_types:
            return self._rejected("testnet_market_order_not_supported", {"symbol": normalized_symbol})

        quantity_decision = self._validate_quantity_filters(rules, quantity)
        if not quantity_decision.allowed:
            return quantity_decision

        notional_decision = self._validate_notional_filters(rules, quantity, market_price)
        if not notional_decision.allowed:
            return notional_decision

        return BinanceOrderValidationDecision(
            allowed=True,
            reason="allowed",
            metadata={"symbol": normalized_symbol, "mode": "testnet", "broker": "binance_testnet"},
        )

    def _validate_quantity_filters(
        self,
        rules: BinanceSymbolRules,
        quantity: Decimal,
    ) -> BinanceOrderValidationDecision:
        filters = [rules.lot_size]
        if rules.market_lot_size is not None and rules.market_lot_size.meaningful:
            filters.append(rules.market_lot_size)
        for quantity_filter in filters:
            if quantity_filter is None or not quantity_filter.meaningful:
                continue
            metadata = {
                "symbol": rules.symbol,
                "quantity": str(quantity),
                "filter_type": quantity_filter.filter_type,
                "min_qty": str(quantity_filter.min_qty),
                "max_qty": str(quantity_filter.max_qty),
                "step_size": str(quantity_filter.step_size),
            }
            if quantity_filter.min_qty > ZERO and quantity < quantity_filter.min_qty:
                return self._rejected("testnet_quantity_below_minimum", metadata)
            if quantity_filter.max_qty > ZERO and quantity > quantity_filter.max_qty:
                return self._rejected("testnet_quantity_above_maximum", metadata)
            if quantity_filter.step_size > ZERO and quantity % quantity_filter.step_size != ZERO:
                return self._rejected("testnet_quantity_step_mismatch", metadata)
        return BinanceOrderValidationDecision(allowed=True, reason="allowed", metadata={})

    def _validate_notional_filters(
        self,
        rules: BinanceSymbolRules,
        quantity: Decimal,
        market_price: Decimal | None,
    ) -> BinanceOrderValidationDecision:
        checks = []
        if rules.min_notional is not None and rules.min_notional.apply_to_market and rules.min_notional.min_notional > ZERO:
            checks.append(("MIN_NOTIONAL", "min", rules.min_notional.min_notional))
        if rules.notional is not None:
            if rules.notional.apply_min_to_market and rules.notional.min_notional > ZERO:
                checks.append(("NOTIONAL", "min", rules.notional.min_notional))
            if rules.notional.apply_max_to_market and rules.notional.max_notional > ZERO:
                checks.append(("NOTIONAL", "max", rules.notional.max_notional))
        if not checks:
            return BinanceOrderValidationDecision(allowed=True, reason="allowed", metadata={})
        if market_price is None or not market_price.is_finite() or market_price <= ZERO:
            return self._rejected("testnet_exchange_info_unavailable", {"symbol": rules.symbol, "market_price_required": True})

        notional = quantity * market_price
        for filter_type, bound, limit in checks:
            metadata = {
                "symbol": rules.symbol,
                "quantity": str(quantity),
                "market_price": str(market_price),
                "notional": str(notional),
                "filter_type": filter_type,
            }
            if bound == "min" and notional < limit:
                return self._rejected("testnet_notional_below_minimum", {**metadata, "min_notional": str(limit)})
            if bound == "max" and notional > limit:
                return self._rejected("testnet_notional_above_maximum", {**metadata, "max_notional": str(limit)})
        return BinanceOrderValidationDecision(allowed=True, reason="allowed", metadata={})

    @staticmethod
    def _rejected(reason: str, metadata: dict[str, Any]) -> BinanceOrderValidationDecision:
        return BinanceOrderValidationDecision(
            allowed=False,
            reason=reason,
            metadata={**metadata, "mode": "testnet", "broker": "binance_testnet"},
        )
