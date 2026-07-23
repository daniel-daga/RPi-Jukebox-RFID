"""Helpers for logging RPC calls without exposing sensitive arguments."""

from typing import Any, Mapping, Tuple


REDACTED = "<redacted>"
_SENSITIVE_CALLS = frozenset({
    ("spotify", "ctrl", "submit_auth_code"),
})


def is_sensitive_call(package: Any, plugin: Any, method: Any) -> bool:
    """Return whether an RPC target accepts credentials or authorization data."""
    return (package, plugin, method) in _SENSITIVE_CALLS


def redact_call_arguments(package: Any, plugin: Any, method: Any,
                          args: Any, kwargs: Any) -> Tuple[Any, Any]:
    """Return arguments suitable for logs, leaving the originals untouched."""
    if is_sensitive_call(package, plugin, method):
        return REDACTED, REDACTED
    return args, kwargs


def redact_request(request: Mapping[str, Any]) -> dict:
    """Return a shallow, log-safe copy of an RPC request."""
    safe_request = dict(request)
    if is_sensitive_call(request.get("package"), request.get("plugin"), request.get("method")):
        if "args" in safe_request:
            safe_request["args"] = REDACTED
        if "kwargs" in safe_request:
            safe_request["kwargs"] = REDACTED
    return safe_request
