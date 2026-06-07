from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.models.execution_attempt import ExecutionAttempt
from app.models.execution_reconciliation_job import ExecutionReconciliationJob
from app.repositories.execution_attempt import ExecutionAttemptRepository
from app.repositories.execution_reconciliation_job import ExecutionReconciliationJobRepository
from app.services.brokers.binance import (
    BinanceInvalidOrderQueryResponseError,
    BinanceOrderHttpResponse,
    BinanceRequestSigner,
    BinanceSignedRequestBuilder,
    BinanceTestnetOrderClient,
    BinanceTestnetOrderQueryClientError,
)
from app.schemas.execution import (
    ExecutionManualReconciliationRead,
    ExecutionReconciliationAttemptRead,
    ExecutionReconciliationStatusRead,
)
from app.services.execution_reconciliation_jobs import ExecutionReconciliationJobService

MANUAL_RECONCILIATION_CONFIG_ERROR = "testnet_reconciliation_config_unavailable"
MANUAL_RECONCILIATION_UPSTREAM_ERROR = "testnet_reconciliation_query_failed"
NON_RECONCILABLE_ERROR = "execution_attempt_not_reconcilable"
UNSAFE_METADATA_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "signature",
        "signed_params",
        "signed_query",
        "signed_url",
        "headers",
        "request_headers",
        "raw_post_body",
        "raw_get_body",
        "raw_request_body",
        "raw_response_body",
        "unsafe_exception",
    }
)


class ExecutionReconciliationStatusService:
    def __init__(
        self,
        repository: ExecutionAttemptRepository,
        *,
        settings: Settings | None = None,
        order_client: BinanceTestnetOrderClient | None = None,
        timestamp_provider=None,
    ):
        self.repository = repository
        self.settings = settings
        self.order_client = order_client
        self.timestamp_provider = timestamp_provider

    def get_bot_status(self, *, bot_id: int, limit: int) -> ExecutionReconciliationStatusRead:
        recent_attempts = self.repository.list_reconciliation_related_for_bot(bot_id=bot_id, limit=limit)
        job_service = ExecutionReconciliationJobService(
            self.repository,
            ExecutionReconciliationJobRepository(self.repository.db),
        )
        job_counts = job_service.counts_for_bot(bot_id=bot_id)
        jobs_by_attempt_id = job_service.jobs_for_attempts(
            bot_id=bot_id,
            attempt_ids=[attempt.id for attempt in recent_attempts],
        )

        return ExecutionReconciliationStatusRead(
            bot_id=bot_id,
            unresolved_unknown_count=self.repository.count_unresolved_reconciliation_for_bot(bot_id=bot_id),
            recovered_count=self.repository.count_recovered_reconciliation_for_bot(bot_id=bot_id),
            latest_unresolved_at=self.repository.latest_unresolved_reconciliation_at_for_bot(bot_id=bot_id),
            latest_recovered_at=self.repository.latest_recovered_reconciliation_at_for_bot(bot_id=bot_id),
            pending_delayed_reconciliation_count=job_counts.pending,
            claimed_delayed_reconciliation_count=job_counts.claimed,
            expired_lease_count=job_counts.expired,
            exhausted_delayed_reconciliation_count=job_counts.exhausted,
            recent_attempts=[
                self._build_attempt_read(attempt, job=jobs_by_attempt_id.get(attempt.id))
                for attempt in recent_attempts
            ],
        )

    def manually_reconcile_attempt(self, *, bot_id: int, attempt_id: int) -> ExecutionManualReconciliationRead:
        attempt = self.repository.get_by_id(attempt_id)
        if attempt is None:
            raise NotFoundError(
                f"Execution attempt with id {attempt_id} was not found",
                error_code="execution_attempt_not_found",
            )
        if attempt.bot_id != bot_id:
            raise ConflictError(
                "Execution attempt does not belong to the selected bot",
                error_code=NON_RECONCILABLE_ERROR,
            )
        if self._submission_recovered(attempt):
            return self._build_manual_read(attempt, already_resolved=True)

        metadata = self._metadata(attempt)
        symbol = self._safe_symbol(attempt.symbol)
        client_order_id = self._safe_string(metadata.get("client_order_id"))
        self._ensure_reconcilable(attempt, metadata, symbol=symbol, client_order_id=client_order_id)
        self._ensure_configured()

        # End any read transaction before the external read-only Binance request.
        self.repository.db.rollback()

        result = self._query_order(symbol=symbol, client_order_id=client_order_id)

        latest = self.repository.get_by_id(attempt_id)
        if latest is None:
            raise NotFoundError(
                f"Execution attempt with id {attempt_id} was not found",
                error_code="execution_attempt_not_found",
            )
        if self._submission_recovered(latest):
            return self._build_manual_read(latest, already_resolved=True)

        latest_metadata = self._safe_metadata(latest)
        manual_count = self._manual_attempt_count(latest_metadata) + 1
        checked_at = self._now_isoformat()

        if result["resolution"] == "found":
            payload = result["payload"]
            latest.metadata_ = {
                **latest_metadata,
                "client_order_id": client_order_id,
                "submission_status_unknown": True,
                "reconciliation_attempted": True,
                "reconciliation_resolution": "found",
                "submission_recovered": True,
                "recovered_order_status": payload["status"],
                "exchange_order_id": str(payload["orderId"]),
                "manual_reconciliation_attempted": True,
                "manual_reconciliation_attempt_count": manual_count,
                "manual_reconciliation_last_checked_at": checked_at,
                "manual_reconciliation_last_resolution": "found",
            }
            latest.metadata_.pop("manual_reconciliation_last_failure_category", None)
            latest.final_status = "order_created"
            latest.final_reason = "testnet_order_recovered_after_unknown_submission"
            self.repository.update(latest)
            ExecutionReconciliationJobService(
                self.repository,
                ExecutionReconciliationJobRepository(self.repository.db),
            ).mark_job_resolved_for_attempt(
                execution_attempt_id=latest.id,
                resolved_at=self._utc_now(),
            )
            self.repository.db.commit()
            self.repository.db.refresh(latest)
            return self._build_manual_read(latest)

        latest.metadata_ = {
            **latest_metadata,
            "client_order_id": client_order_id,
            "submission_status_unknown": True,
            "reconciliation_attempted": True,
            "reconciliation_resolution": "unresolved",
            "submission_recovered": False,
            "manual_reconciliation_attempted": True,
            "manual_reconciliation_attempt_count": manual_count,
            "manual_reconciliation_last_checked_at": checked_at,
            "manual_reconciliation_last_resolution": result["resolution"],
        }
        if result.get("failure_category") is not None:
            latest.metadata_["manual_reconciliation_last_failure_category"] = result["failure_category"]
        else:
            latest.metadata_.pop("manual_reconciliation_last_failure_category", None)
        self.repository.update(latest)
        ExecutionReconciliationJobService(
            self.repository,
            ExecutionReconciliationJobRepository(self.repository.db),
        ).ensure_pending_job_for_persisted_attempt(
            latest,
            initial_delay_seconds=self._settings().binance_testnet_reconciliation_initial_delay_seconds,
        )
        self.repository.db.commit()
        self.repository.db.refresh(latest)

        if result["resolution"] == "failed":
            raise AppError(
                "Binance testnet reconciliation query failed",
                status_code=502,
                error_code=MANUAL_RECONCILIATION_UPSTREAM_ERROR,
            )
        return self._build_manual_read(latest)

    def _build_attempt_read(
        self,
        attempt: ExecutionAttempt,
        *,
        job: ExecutionReconciliationJob | None = None,
    ) -> ExecutionReconciliationAttemptRead:
        metadata = self._metadata(attempt)
        return ExecutionReconciliationAttemptRead(
            attempt_id=attempt.id,
            bot_id=attempt.bot_id,
            created_at=attempt.created_at,
            symbol=attempt.symbol,
            side=attempt.side,
            quantity=attempt.requested_quantity,
            reason=attempt.final_reason,
            new_client_order_id=self._safe_string(metadata.get("client_order_id")),
            submission_status_unknown=bool(metadata.get("submission_status_unknown")),
            reconciliation_attempted=bool(metadata.get("reconciliation_attempted")),
            reconciliation_trigger=self._safe_string(metadata.get("reconciliation_trigger")),
            reconciliation_resolution=self._safe_string(metadata.get("reconciliation_resolution")),
            submission_recovered=self._submission_recovered(attempt),
            recovered_order_status=self._safe_string(metadata.get("recovered_order_status")),
            binance_order_id=self._safe_string(metadata.get("exchange_order_id")),
            delayed_reconciliation_job_id=job.id if job is not None else None,
            delayed_reconciliation_state=job.state if job is not None else None,
            delayed_reconciliation_next_attempt_at=job.next_attempt_at if job is not None else None,
            delayed_reconciliation_lease_expires_at=job.lease_expires_at if job is not None else None,
            delayed_reconciliation_automatic_attempt_count=job.automatic_attempt_count if job is not None else None,
            delayed_reconciliation_last_checked_at=job.last_checked_at if job is not None else None,
            delayed_reconciliation_last_resolution=job.last_resolution if job is not None else None,
            delayed_reconciliation_last_failure_category=job.last_failure_category if job is not None else None,
        )

    def _build_manual_read(self, attempt: ExecutionAttempt, *, already_resolved: bool = False) -> ExecutionManualReconciliationRead:
        metadata = self._metadata(attempt)
        return ExecutionManualReconciliationRead(
            bot_id=attempt.bot_id or 0,
            attempt_id=attempt.id,
            already_resolved=already_resolved,
            submission_status_unknown=bool(metadata.get("submission_status_unknown")),
            submission_recovered=bool(metadata.get("submission_recovered")),
            reconciliation_resolution=self._safe_string(metadata.get("reconciliation_resolution")),
            recovered_order_status=self._safe_string(metadata.get("recovered_order_status")),
            exchange_order_id=self._safe_string(metadata.get("exchange_order_id")),
            new_client_order_id=self._safe_string(metadata.get("client_order_id")),
            manual_reconciliation_attempted=bool(metadata.get("manual_reconciliation_attempted")),
            manual_reconciliation_attempt_count=self._manual_attempt_count(metadata),
            manual_reconciliation_last_checked_at=self._manual_checked_at(metadata),
            manual_reconciliation_last_resolution=self._safe_string(metadata.get("manual_reconciliation_last_resolution")),
            manual_reconciliation_last_failure_category=self._safe_string(
                metadata.get("manual_reconciliation_last_failure_category")
            ),
        )

    def _ensure_reconcilable(
        self,
        attempt: ExecutionAttempt,
        metadata: dict[str, Any],
        *,
        symbol: str | None,
        client_order_id: str | None,
    ) -> None:
        if attempt.mode != "testnet" or attempt.broker != "binance_testnet":
            raise self._not_reconcilable()
        if metadata.get("submission_status_unknown") is not True:
            raise self._not_reconcilable()
        if metadata.get("submission_recovered") is True:
            raise self._not_reconcilable()
        if self._safe_string(metadata.get("reconciliation_resolution")) != "unresolved":
            raise self._not_reconcilable()
        if not symbol or not client_order_id:
            raise self._not_reconcilable()

    def _ensure_configured(self) -> None:
        settings = self._settings()
        if (
            not settings.binance_testnet_broker_enabled
            or not settings.binance_testnet_order_submission_enabled
            or not settings.binance_testnet_api_key
            or not settings.binance_testnet_api_secret
        ):
            raise AppError(
                "Binance testnet reconciliation is not configured",
                status_code=409,
                error_code=MANUAL_RECONCILIATION_CONFIG_ERROR,
            )

    def _query_order(self, *, symbol: str, client_order_id: str) -> dict[str, Any]:
        settings = self._settings()
        request_builder = BinanceSignedRequestBuilder(
            BinanceRequestSigner(settings.binance_testnet_api_secret or "", timestamp_provider=self.timestamp_provider),
            recv_window=settings.binance_testnet_recv_window,
        )
        query_params = request_builder.order_query_params(symbol=symbol, client_order_id=client_order_id)

        try:
            response = self._order_client().query_signed_order(query_params)
        except BinanceTestnetOrderQueryClientError as exc:
            return {"resolution": "failed", "failure_category": self._query_exception_category(exc)}
        except BinanceInvalidOrderQueryResponseError:
            return {"resolution": "failed", "failure_category": "invalid_response"}
        except Exception:
            return {"resolution": "failed", "failure_category": "network_error"}

        if response.status_code < 200 or response.status_code >= 300:
            if self._is_no_such_order(response):
                return {"resolution": "not_found"}
            return {"resolution": "failed", "failure_category": "http_error"}
        if response.payload is None:
            return {"resolution": "failed", "failure_category": "invalid_response"}
        if not self._is_matching_order(response.payload, symbol=symbol, client_order_id=client_order_id):
            return {"resolution": "failed", "failure_category": "mismatched_response"}
        return {"resolution": "found", "payload": response.payload}

    @classmethod
    def _submission_recovered(cls, attempt: ExecutionAttempt) -> bool:
        return bool(cls._metadata(attempt).get("submission_recovered"))

    @staticmethod
    def _not_reconcilable() -> ConflictError:
        return ConflictError(
            "Execution attempt is not eligible for manual reconciliation",
            error_code=NON_RECONCILABLE_ERROR,
        )

    def _settings(self) -> Settings:
        if self.settings is not None:
            return self.settings
        from app.core.config import get_settings

        return get_settings()

    def _order_client(self) -> BinanceTestnetOrderClient:
        if self.order_client is not None:
            return self.order_client
        settings = self._settings()
        return BinanceTestnetOrderClient(
            base_url=settings.binance_testnet_base_url,
            api_key=settings.binance_testnet_api_key or "",
            timeout_seconds=settings.binance_testnet_timeout_seconds,
        )

    def _now_isoformat(self) -> str:
        return self._utc_now().isoformat()

    @staticmethod
    def _metadata(attempt: ExecutionAttempt) -> dict[str, Any]:
        if isinstance(attempt.metadata_, dict):
            return attempt.metadata_
        return {}

    @classmethod
    def _safe_metadata(cls, attempt: ExecutionAttempt) -> dict[str, Any]:
        return {key: value for key, value in cls._metadata(attempt).items() if key not in UNSAFE_METADATA_KEYS}

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
        return None

    @staticmethod
    def _safe_symbol(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        return normalized or None

    @staticmethod
    def _manual_attempt_count(metadata: dict[str, Any]) -> int:
        value = metadata.get("manual_reconciliation_attempt_count")
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    @staticmethod
    def _manual_checked_at(metadata: dict[str, Any]):
        value = metadata.get("manual_reconciliation_last_checked_at")
        if not isinstance(value, str) or not value:
            return None
        from datetime import datetime

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _is_no_such_order(response: BinanceOrderHttpResponse) -> bool:
        return response.payload is not None and response.payload.get("code") == -2013

    @classmethod
    def _is_matching_order(cls, payload: dict, *, symbol: str, client_order_id: str) -> bool:
        response_symbol = payload.get("symbol")
        response_client_order_id = payload.get("clientOrderId")
        status = payload.get("status")
        if not isinstance(response_symbol, str) or response_symbol.strip().upper() != symbol:
            return False
        if not isinstance(response_client_order_id, str) or response_client_order_id != client_order_id:
            return False
        if not cls._valid_order_id(payload.get("orderId")):
            return False
        return isinstance(status, str) and bool(status.strip())

    @staticmethod
    def _valid_order_id(value: Any) -> bool:
        if isinstance(value, int):
            return value >= 0
        if isinstance(value, str):
            return bool(value.strip())
        return False

    @staticmethod
    def _query_exception_category(exc: BinanceTestnetOrderQueryClientError) -> str:
        trigger = getattr(exc, "trigger", None)
        if trigger in {"timeout", "network_error"}:
            return trigger
        if "timeout" in str(exc).lower():
            return "timeout"
        return "network_error"

    @staticmethod
    def _utc_now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)
