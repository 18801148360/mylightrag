"""Authentication helpers for the HTTP MCP transport."""

from __future__ import annotations

import hmac
from typing import Any


class MCPAuthenticationError(PermissionError):
    """Raised when an HTTP MCP request does not have the configured API key."""


def _extract_api_key(headers: Any) -> str | None:
    api_key = headers.get("x-api-key")
    if api_key:
        return api_key.strip()

    authorization = headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def verify_api_key(context: Any, expected_api_key: str | None) -> None:
    """Verify an API key supplied through MCP's HTTP request context.

    stdio has no HTTP headers and is intentionally treated as a local transport.
    When an API key is configured, it is enforced for HTTP requests while the
    local stdio process remains trusted by the operating system boundary.
    """

    if not expected_api_key:
        return

    try:
        request = context.get_http_request()
    except Exception as exc:  # pragma: no cover - depends on FastMCP transport
        raise MCPAuthenticationError("API key authentication is unavailable") from exc

    if request is None:
        return

    supplied_api_key = _extract_api_key(request.headers)
    if not supplied_api_key or not hmac.compare_digest(
        supplied_api_key, expected_api_key
    ):
        raise MCPAuthenticationError("Invalid API key")
