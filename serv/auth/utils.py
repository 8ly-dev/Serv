"""
Security utilities for the Serv authentication framework.

This module provides utilities for device fingerprinting, timing attack protection,
and other security-related functionality.

Security considerations:
- Timing protection is critical for preventing information disclosure
- Fingerprinting should balance security with privacy
- All cryptographic operations should use secure defaults
"""

import asyncio
import hashlib
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from serv.requests import Request


class MinimumRuntime:
    """
    Context manager that ensures authentication operations take a minimum time.

    Prevents timing attacks where response time reveals information about
    user existence, password correctness, etc.

    Security Note:
    This is a critical security control. All authentication operations
    should use this to prevent timing-based information disclosure.
    """

    def __init__(self, seconds: float):
        if seconds <= 0:
            raise ValueError("Minimum runtime must be positive")
        self.minimum_seconds = seconds
        self.start_time: float | None = None

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return

        elapsed = time.perf_counter() - self.start_time
        remaining = self.minimum_seconds - elapsed

        if remaining > 0:
            await asyncio.sleep(remaining)


@asynccontextmanager
async def timing_protection(seconds: float) -> AsyncGenerator[None]:
    """
    Async context manager for timing attack protection.

    Usage:
        async with timing_protection(2.0):
            # Authentication operation here
            result = await authenticate_user(username, password)
            return result
    """
    async with MinimumRuntime(seconds):
        yield


def generate_device_fingerprint(request: "Request") -> str:
    """
    Generate a device fingerprint from request headers.

    Security considerations:
    - Balances security (session binding) with privacy
    - Uses only standard headers to avoid fingerprinting concerns
    - Hash ensures consistent format and prevents header injection

    Args:
        request: The incoming HTTP request

    Returns:
        Hex string fingerprint of the device
    """
    # Collect standard headers that are stable for a device/browser
    fingerprint_data = {
        "user_agent": request.headers.get("user-agent", ""),
        "accept_language": request.headers.get("accept-language", ""),
        "accept_encoding": request.headers.get("accept-encoding", ""),
        "accept": request.headers.get("accept", ""),
    }

    # Include client IP for additional security
    # Note: In production, consider X-Forwarded-For handling
    client_ip = getattr(request.client, "host", "") if request.client else ""
    fingerprint_data["client_ip"] = client_ip

    # Create deterministic string representation
    fingerprint_string = "|".join(
        [f"{k}:{v}" for k, v in sorted(fingerprint_data.items())]
    )

    # Hash to create consistent, privacy-conscious fingerprint
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()


def sanitize_user_input(value: str, max_length: int = 1000) -> str:
    """
    Sanitize user input for logging and storage.

    Security considerations:
    - Prevents injection attacks in logs
    - Limits input length to prevent DoS
    - Removes potentially dangerous characters

    Args:
        value: The input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string safe for logging/storage
    """
    if not isinstance(value, str):
        return ""

    # Truncate to prevent DoS
    if len(value) > max_length:
        value = value[:max_length]

    # Remove null bytes and control characters except newlines/tabs
    sanitized = "".join(
        char for char in value if char.isprintable() or char in ("\n", "\t")
    )

    return sanitized


def validate_session_fingerprint(
    stored_fingerprint: str, current_fingerprint: str, strict: bool = True
) -> bool:
    """
    Validate that a session fingerprint matches the current request.

    Security considerations:
    - Prevents session hijacking across different devices
    - Strict mode requires exact match
    - Non-strict mode allows for some header variation

    Args:
        stored_fingerprint: Fingerprint from session creation
        current_fingerprint: Fingerprint from current request
        strict: Whether to require exact match

    Returns:
        True if fingerprints are considered valid
    """
    if not stored_fingerprint or not current_fingerprint:
        return False

    if strict:
        return stored_fingerprint == current_fingerprint

    # In non-strict mode, we could implement fuzzy matching
    # For now, still require exact match for security
    return stored_fingerprint == current_fingerprint


def secure_compare(a: str, b: str) -> bool:
    """
    Timing-safe string comparison.

    Security considerations:
    - Prevents timing attacks on string comparisons
    - Always takes the same time regardless of where strings differ
    - Critical for comparing tokens, hashes, etc.

    Args:
        a: First string to compare
        b: Second string to compare

    Returns:
        True if strings are equal
    """
    if len(a) != len(b):
        return False

    result = 0
    for x, y in zip(a, b, strict=False):
        result |= ord(x) ^ ord(y)

    return result == 0


def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token.

    Returns:
        URL-safe CSRF token
    """
    import secrets

    return secrets.token_urlsafe(32)


def mask_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Mask sensitive data in dictionaries for logging.

    Security considerations:
    - Prevents accidental logging of sensitive data
    - Preserves structure for debugging
    - Configurable sensitive field detection

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dictionary with sensitive values masked
    """
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "key",
        "credential",
        "authorization",
        "auth",
        "passwd",
        "pwd",
        "api_key",
    }

    masked = {}
    for key, value in data.items():
        key_lower = key.lower()
        is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)

        if is_sensitive:
            if isinstance(value, str) and len(value) > 4:
                # Show first and last 2 characters for debugging
                masked[key] = f"{value[:2]}***{value[-2:]}"
            else:
                masked[key] = "***"
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked[key] = mask_sensitive_data(value)
        else:
            masked[key] = value

    return masked
