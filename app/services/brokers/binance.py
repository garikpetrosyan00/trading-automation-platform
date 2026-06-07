from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import httpx

from app.services.brokers.base import BrokerOrderIntent, BrokerOrderResult
from app.services.brokers.binance_exchange_info import BinanceExchangeInfoProvider, BinanceMarketOrderValidator
from app.services.brokers.safety import ExecutionSafetyConfig, ExecutionSafetyGuard
from app.services.execution_attempt import ExecutionAttemptService

DEFAULT_RECV_WINDOW = 5000
MARKET_ORDER_ENDPOINT = "/api/v3/order"
ACCOUNT_ENDPOINT = "/api/v3/account"
ORDER_QUERY_ENDPOINT = "/api/v3/order"
ZERO = Decimal("0")


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

    def market_order_params(
        self,
        *,
        symbol: str,
        side: str,
        quantity: Decimal,
        client_order_id: str | None = None,
    ) -> dict:
        payload = {
            "symbol": symbol.strip().upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": self._format_decimal(quantity),
        }
        if client_order_id is not None:
            payload["newClientOrderId"] = client_order_id
        return self.signed_params(payload)

    def account_params(self) -> dict:
        return self.signed_params({})

    def order_query_params(self, *, symbol: str, client_order_id: str) -> dict:
        return self.signed_params(
            {
                "symbol": symbol.strip().upper(),
                "origClientOrderId": client_order_id,
            }
        )

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return format(value.normalize(), "f")


@dataclass(frozen=True)
class BinanceOrderHttpResponse:
    status_code: int
    payload: dict | None


@dataclass(frozen=True)
class BinanceAccountHttpResponse:
    status_code: int
    payload: dict | None


@dataclass(frozen=True)
class BinanceAccountPreflightResult:
    allowed: bool
    reason: str
    message: str
    metadata: dict


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
        except httpx.TimeoutException as exc:
            raise BinanceTestnetOrderClientError(
                "Could not reach Binance testnet order endpoint",
                trigger="timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise BinanceTestnetOrderClientError(
                "Could not reach Binance testnet order endpoint",
                trigger="network_error",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceInvalidOrderResponseError("Binance testnet order endpoint returned invalid JSON") from exc

        if payload is not None and not isinstance(payload, dict):
            raise BinanceInvalidOrderResponseError("Binance testnet order endpoint returned invalid JSON")

        return BinanceOrderHttpResponse(status_code=response.status_code, payload=payload)

    def query_signed_order(self, params: dict) -> BinanceOrderHttpResponse:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.get(
                    ORDER_QUERY_ENDPOINT,
                    params=params,
                    headers={"X-MBX-APIKEY": self.api_key},
                )
        except httpx.TimeoutException as exc:
            raise BinanceTestnetOrderQueryClientError(
                "Could not reach Binance testnet order query endpoint",
                trigger="timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise BinanceTestnetOrderQueryClientError(
                "Could not reach Binance testnet order query endpoint",
                trigger="network_error",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceInvalidOrderQueryResponseError("Binance testnet order query endpoint returned invalid JSON") from exc

        if payload is not None and not isinstance(payload, dict):
            raise BinanceInvalidOrderQueryResponseError("Binance testnet order query endpoint returned invalid JSON")

        return BinanceOrderHttpResponse(status_code=response.status_code, payload=payload)


class BinanceTestnetAccountClient:
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

    def fetch_signed_account(self, params: dict) -> BinanceAccountHttpResponse:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.get(
                    ACCOUNT_ENDPOINT,
                    params=params,
                    headers={"X-MBX-APIKEY": self.api_key},
                )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise BinanceTestnetAccountClientError("Could not reach Binance testnet account endpoint") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BinanceInvalidAccountResponseError("Binance testnet account endpoint returned invalid JSON") from exc

        if payload is not None and not isinstance(payload, dict):
            raise BinanceInvalidAccountResponseError("Binance testnet account endpoint returned invalid JSON")

        return BinanceAccountHttpResponse(status_code=response.status_code, payload=payload)


class BinanceTestnetOrderClientError(Exception):
    def __init__(self, message: str, *, trigger: str | None = None):
        super().__init__(message)
        self.trigger = trigger


class BinanceInvalidOrderResponseError(Exception):
    pass


class BinanceTestnetOrderQueryClientError(Exception):
    def __init__(self, message: str, *, trigger: str | None = None):
        super().__init__(message)
        self.trigger = trigger


class BinanceInvalidOrderQueryResponseError(Exception):
    pass


class BinanceTestnetAccountClientError(Exception):
    pass


class BinanceInvalidAccountResponseError(Exception):
    pass


class BinanceTestnetBroker:
    def __init__(
        self,
        config: BinanceTestnetBrokerConfig,
        http_client=None,
        account_client=None,
        exchange_info_provider: BinanceExchangeInfoProvider | None = None,
        safety_guard: ExecutionSafetyGuard | None = None,
        attempt_service: ExecutionAttemptService | None = None,
    ):
        self.config = config
        self.http_client = http_client
        self.account_client = account_client
        self.exchange_info_provider = exchange_info_provider
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
        safety_decision = self.safety_guard.validate_order(
            safety_intent,
            broker="binance_testnet",
            market_price=intent.market_price,
        )
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

        exchange_info_decision = self._validate_exchange_info(normalized_symbol, intent)
        if not exchange_info_decision.accepted:
            self._record_attempt(intent, exchange_info_decision, final_status="rejected_by_broker", safety_status="allowed")
            return exchange_info_decision

        account_preflight = self._validate_account_preflight(intent, exchange_info_decision.metadata)
        if not account_preflight.allowed:
            result = self._rejected(
                account_preflight.message,
                reason=account_preflight.reason,
                metadata=account_preflight.metadata,
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        client_order_id = self._generate_client_order_id()
        signed_params = self._build_signed_market_order_params(
            symbol=normalized_symbol,
            side=intent.side,
            quantity=intent.quantity,
            client_order_id=client_order_id,
        )
        if self.config.dry_run_enabled:
            result = BrokerOrderResult(
                accepted=False,
                status="rejected",
                message="Binance testnet order submission dry run prepared",
                reason="testnet_order_submission_dry_run",
                metadata=self._safe_signed_request_metadata(signed_params, intent, account_preflight.metadata),
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        if self.http_client is None:
            result = self._rejected(
                "Binance testnet order submission is not implemented",
                reason="testnet_order_submission_not_implemented",
                metadata=self._safe_signed_request_metadata(signed_params, intent, account_preflight.metadata),
            )
            self._record_attempt(intent, result, final_status="rejected_by_broker", safety_status="allowed")
            return result

        result = self._submit_signed_order(intent, signed_params, account_preflight.metadata)
        if result.accepted:
            quota_metadata = self._record_successful_daily_quota(intent)
            if quota_metadata:
                result = replace(result, metadata={**result.metadata, **quota_metadata})
        self._record_attempt(
            intent,
            result,
            final_status="order_created" if result.accepted else "rejected_by_broker",
            safety_status="allowed",
        )
        return result

    def _validate_exchange_info(self, normalized_symbol: str, intent: BrokerOrderIntent) -> BrokerOrderResult:
        if self.exchange_info_provider is None:
            return self._rejected(
                "Binance testnet exchange info is unavailable",
                reason="testnet_exchange_info_unavailable",
                metadata={"symbol": normalized_symbol, "mode": "testnet", "broker": "binance_testnet"},
            )
        decision = BinanceMarketOrderValidator(self.exchange_info_provider).validate(
            symbol=normalized_symbol,
            quantity=intent.quantity,
            market_price=intent.market_price,
        )
        if decision.allowed:
            return BrokerOrderResult(
                accepted=True,
                status="validated",
                message="Binance testnet exchange info validation passed",
                metadata=decision.metadata,
            )
        return self._rejected(
            decision.reason,
            reason=decision.reason,
            metadata=decision.metadata,
        )

    def _record_successful_daily_quota(self, intent: BrokerOrderIntent) -> dict:
        daily_limit_service = self.safety_guard.daily_limit_service
        if daily_limit_service is None:
            return {}
        reservation = daily_limit_service.reserve_accepted_order_quota(
            bot_id=intent.bot_id,
            max_daily_order_count=self.safety_guard.config.max_daily_order_count,
            enforce_limit=False,
        )
        return {
            "daily_order_count": reservation.count,
            "max_daily_order_count": reservation.max_daily_order_count,
            "utc_day": reservation.utc_day.isoformat(),
        }

    def _validate_account_preflight(self, intent: BrokerOrderIntent, exchange_metadata: dict) -> BinanceAccountPreflightResult:
        if self.request_builder is None or self.account_client is None:
            return self._account_preflight_rejected(
                "testnet_account_fetch_failed",
                "Binance testnet account preflight could not be performed",
                exchange_metadata,
                balance_asset=None,
                balance_sufficient=False,
            )

        balance_asset = self._balance_asset_for_intent(intent, exchange_metadata)
        if balance_asset is None:
            return self._account_preflight_rejected(
                "testnet_account_response_invalid",
                "Binance testnet account preflight response was invalid",
                exchange_metadata,
                balance_asset=None,
                balance_sufficient=False,
            )

        if intent.side == "buy" and (intent.market_price is None or not intent.market_price.is_finite() or intent.market_price <= ZERO):
            return self._account_preflight_rejected(
                "testnet_account_response_invalid",
                "Binance testnet account preflight response was invalid",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
            )

        signed_params = self.request_builder.account_params()
        try:
            response = self.account_client.fetch_signed_account(signed_params)
        except BinanceTestnetAccountClientError:
            return self._account_preflight_rejected(
                "testnet_account_fetch_failed",
                "Binance testnet account preflight request failed",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
            )
        except BinanceInvalidAccountResponseError:
            return self._account_preflight_rejected(
                "testnet_account_response_invalid",
                "Binance testnet account preflight response was invalid",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
            )
        except Exception:
            return self._account_preflight_rejected(
                "testnet_account_fetch_failed",
                "Binance testnet account preflight request failed",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
            )

        if response.status_code < 200 or response.status_code >= 300:
            return self._account_preflight_rejected(
                "testnet_account_fetch_failed",
                "Binance testnet account preflight request failed",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
                status_code=response.status_code,
            )
        if response.payload is None:
            return self._account_preflight_rejected(
                "testnet_account_response_invalid",
                "Binance testnet account preflight response was invalid",
                exchange_metadata,
                balance_asset=balance_asset,
                balance_sufficient=False,
                status_code=response.status_code,
            )

        balance_decision = self._validate_account_balance(
            response.payload,
            intent=intent,
            balance_asset=balance_asset,
        )
        if not balance_decision.allowed:
            metadata = {
                **exchange_metadata,
                **balance_decision.metadata,
            }
            return BinanceAccountPreflightResult(
                allowed=False,
                reason=balance_decision.reason,
                message=balance_decision.message,
                metadata=metadata,
            )

        return BinanceAccountPreflightResult(
            allowed=True,
            reason="allowed",
            message="Binance testnet account preflight passed",
            metadata={**exchange_metadata, **balance_decision.metadata},
        )

    def _validate_account_balance(
        self,
        payload: dict,
        *,
        intent: BrokerOrderIntent,
        balance_asset: str,
    ) -> BinanceAccountPreflightResult:
        if payload.get("canTrade") is not True:
            return self._account_preflight_rejected(
                "testnet_account_trading_disabled",
                "Binance testnet account trading is disabled",
                {},
                balance_asset=balance_asset,
                balance_sufficient=False,
            )
        balances = payload.get("balances")
        if not isinstance(balances, list):
            return self._account_preflight_rejected(
                "testnet_account_response_invalid",
                "Binance testnet account preflight response was invalid",
                {},
                balance_asset=balance_asset,
                balance_sufficient=False,
            )

        free_balance = ZERO
        found_balance = False
        for balance in balances:
            if not isinstance(balance, dict):
                return self._account_preflight_rejected(
                    "testnet_account_response_invalid",
                    "Binance testnet account preflight response was invalid",
                    {},
                    balance_asset=balance_asset,
                    balance_sufficient=False,
                )
            asset = balance.get("asset")
            if not isinstance(asset, str) or not asset.strip():
                continue
            if asset.strip().upper() != balance_asset:
                continue
            free_balance = self._required_balance_decimal(balance.get("free"))
            if free_balance is None:
                return self._account_preflight_rejected(
                    "testnet_account_response_invalid",
                    "Binance testnet account preflight response was invalid",
                    {},
                    balance_asset=balance_asset,
                    balance_sufficient=False,
                )
            found_balance = True
            break

        required_balance = intent.quantity * intent.market_price if intent.side == "buy" else intent.quantity
        if not found_balance or free_balance < required_balance:
            return self._account_preflight_rejected(
                "testnet_insufficient_balance",
                "Binance testnet account has insufficient available balance",
                {},
                balance_asset=balance_asset,
                balance_sufficient=False,
            )

        return BinanceAccountPreflightResult(
            allowed=True,
            reason="allowed",
            message="Binance testnet account preflight passed",
            metadata={
                "account_preflight_checked": True,
                "balance_asset": balance_asset,
                "balance_sufficient": True,
            },
        )

    @staticmethod
    def _balance_asset_for_intent(intent: BrokerOrderIntent, exchange_metadata: dict) -> str | None:
        key = "quote_asset" if intent.side == "buy" else "base_asset"
        asset = exchange_metadata.get(key)
        if not isinstance(asset, str) or not asset.strip():
            return None
        return asset.strip().upper()

    @staticmethod
    def _required_balance_decimal(value) -> Decimal | None:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not decimal_value.is_finite() or decimal_value < ZERO:
            return None
        return decimal_value

    @staticmethod
    def _account_preflight_rejected(
        reason: str,
        message: str,
        exchange_metadata: dict,
        *,
        balance_asset: str | None,
        balance_sufficient: bool,
        status_code: int | None = None,
    ) -> BinanceAccountPreflightResult:
        metadata = {
            **exchange_metadata,
            "account_preflight_checked": True,
            "balance_sufficient": balance_sufficient,
        }
        if balance_asset is not None:
            metadata["balance_asset"] = balance_asset
        if status_code is not None:
            metadata["account_status_code"] = status_code
        return BinanceAccountPreflightResult(
            allowed=False,
            reason=reason,
            message=message,
            metadata=metadata,
        )

    def _submit_signed_order(
        self,
        intent: BrokerOrderIntent,
        signed_params: dict,
        account_preflight_metadata: dict,
    ) -> BrokerOrderResult:
        try:
            response = self.http_client.submit_signed_market_order(signed_params)
        except (BinanceTestnetOrderClientError, BinanceInvalidOrderResponseError) as exc:
            return self._reconcile_status_unknown_submission(
                intent,
                signed_params,
                account_preflight_metadata,
                trigger=self._exception_reconciliation_trigger(exc),
            )
        except Exception:
            return self._reconcile_status_unknown_submission(
                intent,
                signed_params,
                account_preflight_metadata,
                trigger="network_error",
            )

        if response.payload is None:
            return self._reconcile_status_unknown_submission(
                intent,
                signed_params,
                account_preflight_metadata,
                trigger="invalid_success_response",
                status_code=response.status_code,
            )

        if response.status_code < 200 or response.status_code >= 300:
            if self._is_uncertain_order_response(response):
                return self._reconcile_status_unknown_submission(
                    intent,
                    signed_params,
                    account_preflight_metadata,
                    trigger=self._uncertain_response_trigger(response),
                    status_code=response.status_code,
                )
            reason = "binance_testnet_order_rejected"
            message = self._binance_error_message(response.payload, response.status_code)
            return self._rejected(
                message,
                reason=reason,
                metadata={
                    **self._safe_signed_request_metadata(signed_params, intent, account_preflight_metadata),
                    "status_code": response.status_code,
                    "binance_code": response.payload.get("code"),
                },
            )

        if not self._is_usable_success_payload(response.payload, signed_params):
            return self._reconcile_status_unknown_submission(
                intent,
                signed_params,
                account_preflight_metadata,
                trigger="invalid_success_response",
                status_code=response.status_code,
            )

        return self._build_success_result(intent, signed_params, response, account_preflight_metadata)

    def _reconcile_status_unknown_submission(
        self,
        intent: BrokerOrderIntent,
        signed_params: dict,
        account_preflight_metadata: dict,
        *,
        trigger: str,
        status_code: int | None = None,
    ) -> BrokerOrderResult:
        base_metadata = {
            **self._safe_signed_request_metadata(signed_params, intent, account_preflight_metadata),
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_trigger": trigger,
        }
        if status_code is not None:
            base_metadata["status_code"] = status_code

        if self.request_builder is None or not hasattr(self.http_client, "query_signed_order"):
            return self._unresolved_reconciliation_result(base_metadata)

        query_params = self.request_builder.order_query_params(
            symbol=signed_params["symbol"],
            client_order_id=signed_params["newClientOrderId"],
        )
        try:
            response = self.http_client.query_signed_order(query_params)
        except (BinanceTestnetOrderQueryClientError, BinanceInvalidOrderQueryResponseError):
            return self._unresolved_reconciliation_result(base_metadata)
        except Exception:
            return self._unresolved_reconciliation_result(base_metadata)

        if response.status_code < 200 or response.status_code >= 300:
            return self._unresolved_reconciliation_result(base_metadata)
        if response.payload is None:
            return self._unresolved_reconciliation_result(base_metadata)

        payload = response.payload
        if not self._is_matching_recovered_order(payload, signed_params):
            return self._unresolved_reconciliation_result(base_metadata)

        recovered_response = BinanceOrderHttpResponse(status_code=response.status_code, payload=payload)
        result = self._build_success_result(
            intent,
            signed_params,
            recovered_response,
            {
                **account_preflight_metadata,
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_trigger": trigger,
                "reconciliation_resolution": "found",
                "submission_recovered": True,
                "recovered_order_status": payload["status"],
            },
        )
        return replace(
            result,
            reason="testnet_order_recovered_after_unknown_submission",
            message="Binance testnet order recovered after status-unknown submission",
        )

    @staticmethod
    def _unresolved_reconciliation_result(metadata: dict) -> BrokerOrderResult:
        return BrokerOrderResult(
            accepted=False,
            status="rejected",
            message="Binance testnet order submission status is unresolved after one reconciliation query",
            reason="testnet_order_reconciliation_unresolved",
            metadata={
                **metadata,
                "reconciliation_resolution": "unresolved",
                "submission_recovered": False,
            },
        )

    @staticmethod
    def _is_uncertain_order_response(response: BinanceOrderHttpResponse) -> bool:
        if response.status_code >= 500:
            return True
        code = response.payload.get("code") if response.payload is not None else None
        return code in {-1006, -1007}

    @staticmethod
    def _uncertain_response_trigger(response: BinanceOrderHttpResponse) -> str:
        code = response.payload.get("code") if response.payload is not None else None
        if code in {-1006, -1007}:
            return "binance_unknown_status_error"
        if response.status_code >= 500:
            return "http_5xx"
        return "invalid_success_response"

    @staticmethod
    def _exception_reconciliation_trigger(exc: Exception) -> str:
        trigger = getattr(exc, "trigger", None)
        if trigger in {"timeout", "network_error"}:
            return trigger
        if isinstance(exc, BinanceInvalidOrderResponseError):
            return "invalid_success_response"
        message = str(exc).lower()
        if "timeout" in message:
            return "timeout"
        return "network_error"

    @classmethod
    def _is_usable_success_payload(cls, payload: dict, signed_params: dict) -> bool:
        symbol = payload.get("symbol")
        if isinstance(symbol, str) and symbol.strip().upper() != signed_params["symbol"]:
            return False
        client_order_id = payload.get("clientOrderId")
        if isinstance(client_order_id, str) and client_order_id != signed_params["newClientOrderId"]:
            return False
        return cls._valid_order_id(payload.get("orderId")) and cls._valid_status(payload.get("status"))

    @classmethod
    def _is_matching_recovered_order(cls, payload: dict, signed_params: dict) -> bool:
        symbol = payload.get("symbol")
        client_order_id = payload.get("clientOrderId")
        if not isinstance(symbol, str) or not symbol.strip():
            return False
        if symbol.strip().upper() != signed_params["symbol"]:
            return False
        if not isinstance(client_order_id, str) or not client_order_id:
            return False
        if client_order_id != signed_params["newClientOrderId"]:
            return False
        return cls._valid_order_id(payload.get("orderId")) and cls._valid_status(payload.get("status"))

    @staticmethod
    def _valid_order_id(value) -> bool:
        if isinstance(value, int):
            return value >= 0
        if isinstance(value, str):
            return bool(value.strip())
        return False

    @staticmethod
    def _valid_status(value) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def _build_success_result(
        self,
        intent: BrokerOrderIntent,
        signed_params: dict,
        response: BinanceOrderHttpResponse,
        account_preflight_metadata: dict,
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
                **self._safe_signed_request_metadata(signed_params, intent, account_preflight_metadata),
                "status_code": response.status_code,
                "exchange_status": payload.get("status"),
                "exchange_order_id": external_order_id,
                "exchange_client_order_id": payload.get("clientOrderId"),
            },
        )

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

    def _build_signed_market_order_params(
        self,
        *,
        symbol: str,
        side: str,
        quantity: Decimal,
        client_order_id: str,
    ) -> dict:
        if self.request_builder is None:
            raise ValueError("Binance signed request builder requires an API secret")
        return self.request_builder.market_order_params(
            symbol=symbol,
            side=side,
            quantity=quantity,
            client_order_id=client_order_id,
        )

    @staticmethod
    def _generate_client_order_id() -> str:
        return f"tap_{uuid.uuid4().hex}"

    def _safe_signed_request_metadata(
        self,
        signed_params: dict,
        intent: BrokerOrderIntent,
        account_preflight_metadata: dict | None = None,
    ) -> dict:
        return {
            **(account_preflight_metadata or {}),
            "base_url": self.config.base_url,
            "endpoint_path": MARKET_ORDER_ENDPOINT,
            "method": "POST",
            "symbol": signed_params["symbol"],
            "side": signed_params["side"],
            "order_type": signed_params["type"],
            "quantity": signed_params["quantity"],
            "client_order_id": signed_params.get("newClientOrderId"),
            "signed": bool(signed_params.get("signature")),
            "credentials_configured": bool(self.config.api_key and self.config.api_secret),
            "dry_run": self.config.dry_run_enabled,
            "mode": "testnet",
            "broker": "binance_testnet",
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
            requested_price=intent.market_price,
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
