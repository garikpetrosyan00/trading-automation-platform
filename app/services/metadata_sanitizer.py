from typing import Any

SENSITIVE_METADATA_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "headers",
        "lease_token",
        "raw_get_body",
        "raw_payload",
        "raw_post_body",
        "raw_request_body",
        "raw_response",
        "raw_response_body",
        "request_headers",
        "signature",
        "signed_params",
        "signed_query",
        "signed_url",
        "unsafe_exception",
    }
)

PUBLIC_INTERNAL_IDENTIFIER_KEYS = frozenset(
    {
        "client_order_id",
        "exchange_client_order_id",
        "exchange_order_id",
        "newclientorderid",
        "newClientOrderId",
        "orderid",
        "orderId",
        "origclientorderid",
        "origClientOrderId",
    }
)

PUBLIC_UNSAFE_METADATA_KEYS = SENSITIVE_METADATA_KEYS | PUBLIC_INTERNAL_IDENTIFIER_KEYS
PUBLIC_UNSAFE_METADATA_KEY_LOOKUP = {key.lower() for key in PUBLIC_UNSAFE_METADATA_KEYS}


def sanitize_public_metadata(metadata: Any) -> dict | None:
    if not isinstance(metadata, dict):
        return None
    return {
        key: _sanitize_public_value(value)
        for key, value in metadata.items()
        if _is_public_metadata_key(key)
    }


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_public_value(nested_value)
            for key, nested_value in value.items()
            if _is_public_metadata_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_public_value(item) for item in value]
    return value


def _is_public_metadata_key(key: Any) -> bool:
    return not isinstance(key, str) or key.lower() not in PUBLIC_UNSAFE_METADATA_KEY_LOOKUP
