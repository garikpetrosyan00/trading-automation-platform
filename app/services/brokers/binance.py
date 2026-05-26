from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import httpx

from app.services.brokers.base import BrokerOrderIntent, BrokerOrderResult
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService

DEFAULT_RECV_WINDOW = 5000
MARKET_ORDER_ENDPOINT = "/api/v3/order"


@dataclass(frozen=True)
class BinanceTestnetBrokerConfig:
    enabled: bool = False
    order_submission_enabled: bool = False
    dry_run_enabled: bool = False
    base_url: str = "https://testnet.binance.vision"
    api_key: str | None = None
    api_secret: str | None = None
    recv_window: int = DEFAULT_RECV_WINDOW


class BinanceRequestSigner:
    def __init__(self, api_secret: str, timestamp_provider=None):
        self.api_secret = api_secret
        self.timestamp_provider = timestamp_provider or self.current_timestamp_ms

    def timestamp_ms(self) -> int:
        return int(self.timestamp_provider())

    def sign(self, params: dict) -> str:
        query_string = self.query_string(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def current_timestamp_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    @staticmethod
    def query_string(params: dict) -> str:
        return urlencode([(key, str(value)) for key, value in params.items()])


class BinanceSignedRequestBuilder:
    def __init__(self, signer: BinanceRequestSigner, recv_window: int = DEFAULT_RECV_WINDOW):
        self.signer = signer
        self.recv_window = recv_window

    def signed_params(self, payload: dict) -> dict:
        params = dict(payload)
        params["timestamp"] = self.signer.timestamp_ms()
        params["recvWindow"] = self.recv_window
        params["signature"] = self.signer.sign(params)
        return params

    def market_order_params(self, *, symbol: str, side: str, quantity: Decimal) -> dict:
        payload = {
            "symbol": symbol.strip().upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": self._format_decimal(quantity),
        }
        return self.signed_params(payload)

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return format(value.normalize(), "f")


@dataclass(frozen=True)
class BinanceOrderHttpResponse:
    status_code: int
    payload: dict | None


class BinanceTestnetOrderClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def submit_signed_market_order(self, params: dict) -> BinanceOrderHttpResponse:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    MARKET_ORDER_ENDPOINT,
                    data=params,
                    headers={"X-MBX-APIKEY": self.api_key},
                )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise BinanceTestnetOrderClientError("Could not reach Binance testnet order endpoint") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceInvalidOrderResponseError("Binance testnet order endpoint returned invalid JSON") from exc

        if payload is not None and not isinstance(payload, dict):
            raise BinanceInvalidOrderResponseError("Binance testnet order endpoint returned invalid JSON")

        return BinanceOrderHttpResponse(status_code=response.status_code, payload=payload)


class BinanceTestnetOrderClientError(Exception):
    pass


class BinanceInvalidOrderResponseError(Exception):
    pass


class BinanceTestnetBroker:
    def __init__(
        self,
        config: BinanceTestnetBrokerConfig,
        http_client=None,
        safety_guard: ExecutionSafetyGuard | None = None,
        attempt_service: ExecutionAttemptService | None = None,
    ):
        self.config = config
        self.http_client = http_client
        self.attempt_service = attempt_service
        self.request_builder = (
            BinanceSignedRequestBuilder(BinanceRequestSigner(config.api_secret), recv_window=config.recv_window)
            if config.api_secret
            else None
        )
        self.safety_guard = safety_guard or ExecutionSafetyGuard(
            ExecutionSafetyConfig(testnet_order_submission_enabled=config.order_submission_enabled)
        )

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
            result = self._rejected(
                "Binance testnet broker is disabled",
                reason="testnet_broker_disabled",
                metadata={"base_url": self.config.base_url},
            )
            self._record_attempt(intent, result, final_status="blocked_by_safety", safety_status=result.reason)
            return result

        if not self.config.order_submission_enabled:
            result = self._rejected(
                "Binance testnet order submission is disabled",
                reason="testnet_order_submission_disabled",
                metadata={"base_url": self.config.base_url},
            )
            self._record_attempt(intent, result, final_status="blocked_by_safety", safety_status=result.reason)
            return result

        safety_intent = BrokerOrderIntent(
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            bot_id=intent.bot_id,
            strategy_id=intent.strategy_id,
            order_type=intent.order_type,
            mode="testnet",
            decision_reason=intent.decision_reason,
            decision_metadata=intent.decision_metadata,
        )
        safety_decision = self.safety_guard.validate_order(safety_intent, broker="binance_testnet")
        if not safety_decision.allowed:
            result = self._rejected(
                safety_decision.reason,
                reason=safety_decision.reason,
                metadata=safety_decision.metadata,
            )
            self._record_attempt(intent, result, final_status="blocked_by_safety", safety_status=result.reason)
            return result

        if not self.config.api_key or not self.config.api_secret:
            result = self._rejected(
                "Binance testnet API credentials are not configured",
                reason="missing_testnet_credentials",
                metadata={"base_url": self.config.base_url},
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        signed_params = self._build_signed_market_order_params(
            symbol=normalized_symbol,
            side=intent.side,
            quantity=intent.quantity,
        )
        if self.config.dry_run_enabled:
            result = BrokerOrderResult(
                accepted=False,
                status="rejected",
                message="Binance testnet order submission dry run prepared",
                reason="testnet_order_submission_dry_run",
                metadata=self._safe_signed_request_metadata(signed_params, intent),
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        if self.http_client is None:
            result = self._rejected(
                "Binance testnet order submission is not implemented",
                reason="testnet_order_submission_not_implemented",
                metadata=self._safe_signed_request_metadata(signed_params, intent),
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        result = self._submit_signed_order(intent, signed_params)
        self._record_attempt(
            intent,
            result,
            final_status="order_created" if result.accepted else "rejected_by_broker",
            safety_status="allowed",
        )
        return result

    def _submit_signed_order(self, intent: BrokerOrderIntent, signed_params: dict) -> BrokerOrderResult:
        try:
            response = self.http_client.submit_signed_market_order(signed_params)
        except (BinanceTestnetOrderClientError, BinanceInvalidOrderResponseError) as exc:
            return self._rejected(
                str(exc),
                reason=self._exception_reason(exc),
                metadata={
                    **self._safe_signed_request_metadata(signed_params, intent),
                    "error_type": exc.__class__.__name__,
                },
            )
        except Exception as exc:
            return self._rejected(
                "Binance testnet order request failed",
                reason="binance_testnet_request_failed",
                metadata={
                    **self._safe_signed_request_metadata(signed_params, intent),
                    "error_type": exc.__class__.__name__,
                },
            )

        if response.payload is None:
            return self._rejected(
                "Binance testnet order endpoint returned invalid JSON",
                reason="invalid_binance_response",
                metadata={
                    **self._safe_signed_request_metadata(signed_params, intent),
                    "status_code": response.status_code,
                },
            )

        if response.status_code < 200 or response.status_code >= 300:
            reason = "binance_testnet_order_rejected"
            message = self._binance_error_message(response.payload, response.status_code)
            return self._rejected(
                message,
                reason=reason,
                metadata={
                    **self._safe_signed_request_metadata(signed_params, intent),
                    "status_code": response.status_code,
                    "binance_code": response.payload.get("code"),
                },
            )

        return self._build_success_result(intent, signed_params, response)

    def _build_success_result(
        self,
        intent: BrokerOrderIntent,
        signed_params: dict,
        response: BinanceOrderHttpResponse,
    ) -> BrokerOrderResult:
        payload = response.payload or {}
        external_order_id = str(payload["orderId"]) if payload.get("orderId") is not None else None
        executed_quantity = self._optional_decimal(payload.get("executedQty"))
        executed_price = self._derive_executed_price(payload, executed_quantity)
        fee = self._derive_fee(payload)

        return BrokerOrderResult(
            accepted=True,
            status="submitted",
            message="Binance testnet market order submitted",
            external_order_id=external_order_id,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            fee=fee,
            metadata={
                **self._safe_signed_request_metadata(signed_params, intent),
                "status_code": response.status_code,
                "exchange_status": payload.get("status"),
                "client_order_id_present": payload.get("clientOrderId") is not None,
            },
        )

    @staticmethod
    def _exception_reason(exc: Exception) -> str:
        if isinstance(exc, BinanceInvalidOrderResponseError):
            return "invalid_binance_response"
        return "binance_testnet_request_failed"

    @staticmethod
    def _binance_error_message(payload: dict, status_code: int) -> str:
        message = payload.get("msg") if isinstance(payload.get("msg"), str) else None
        if message:
            return f"Binance testnet order rejected: {message}"
        return f"Binance testnet order request failed with status {status_code}"

    @classmethod
    def _derive_executed_price(cls, payload: dict, executed_quantity: Decimal | None) -> Decimal | None:
        quote_quantity = cls._optional_decimal(payload.get("cummulativeQuoteQty"))
        if quote_quantity is not None and executed_quantity is not None and executed_quantity > 0:
            return quote_quantity / executed_quantity

        fills = payload.get("fills")
        if not isinstance(fills, list) or not fills:
            return None

        total_quantity = Decimal("0")
        total_quote = Decimal("0")
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            price = cls._optional_decimal(fill.get("price"))
            quantity = cls._optional_decimal(fill.get("qty"))
            if price is None or quantity is None:
                continue
            total_quantity += quantity
            total_quote += price * quantity
        if total_quantity <= 0:
            return None
        return total_quote / total_quantity

    @classmethod
    def _derive_fee(cls, payload: dict) -> Decimal | None:
        fills = payload.get("fills")
        if not isinstance(fills, list):
            return None
        fee = Decimal("0")
        found_fee = False
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            commission = cls._optional_decimal(fill.get("commission"))
            if commission is None:
                continue
            fee += commission
            found_fee = True
        return fee if found_fee else None

    @staticmethod
    def _optional_decimal(value) -> Decimal | None:
        if value is None:
            return None
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not decimal_value.is_finite():
            return None
        return decimal_value

    def _build_signed_market_order_params(self, *, symbol: str, side: str, quantity: Decimal) -> dict:
        if self.request_builder is None:
            raise ValueError("Binance signed request builder requires an API secret")
        return self.request_builder.market_order_params(symbol=symbol, side=side, quantity=quantity)

    def _safe_signed_request_metadata(self, signed_params: dict, intent: BrokerOrderIntent) -> dict:
        return {
            "base_url": self.config.base_url,
            "endpoint_path": MARKET_ORDER_ENDPOINT,
            "method": "POST",
            "symbol": signed_params["symbol"],
            "side": signed_params["side"],
            "order_type": signed_params["type"],
            "quantity": signed_params["quantity"],
            "has_signature": bool(signed_params.get("signature")),
            "credentials_configured": bool(self.config.api_key and self.config.api_secret),
            "dry_run": self.config.dry_run_enabled,
            "mode": "testnet",
            "bot_id": intent.bot_id,
            "strategy_id": intent.strategy_id,
        }

    def _record_attempt(
        self,
        intent: BrokerOrderIntent,
        result: BrokerOrderResult,
        *,
        final_status: str,
        safety_status: str | None,
    ) -> None:
        if self.attempt_service is None:
            return
        self.attempt_service.record(
            bot_id=intent.bot_id,
            strategy_id=intent.strategy_id,
            symbol=intent.symbol,
            side=intent.side,
            mode="testnet",
            broker="binance_testnet",
            requested_quantity=intent.quantity,
            requested_price=None,
            decision_reason=intent.decision_reason,
            risk_status=None,
            safety_status=safety_status,
            final_status=final_status,
            final_reason=result.reason or result.message,
            metadata=result.metadata,
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
