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
    from serv.http import Request


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


def get_client_ip(request: "Request", trusted_proxies: list[str] | None = None) -> str:
    """
    Extract real client IP address with X-Forwarded-For support.

    Security considerations:
    - Validates trusted proxy sources to prevent IP spoofing
    - Handles multiple proxy scenarios (CDN, load balancer, etc.)
    - Falls back to direct connection IP if headers are untrusted
    - Prevents header injection attacks

    Args:
        request: The incoming HTTP request
        trusted_proxies: List of trusted proxy IPs/networks (CIDR notation supported)

    Returns:
        Real client IP address as string
    """
    import ipaddress

    # Get direct connection IP
    direct_ip = getattr(request.client, "host", "") if request.client else ""

    # If no trusted proxies configured, return direct IP
    if not trusted_proxies:
        return direct_ip

    # Check if request is coming from a trusted proxy
    def is_trusted_proxy(ip: str) -> bool:
        if not ip:
            return False
        try:
            ip_obj = ipaddress.ip_address(ip)
            for trusted in trusted_proxies:
                try:
                    # Handle CIDR notation (e.g., "10.0.0.0/8")
                    if "/" in trusted:
                        network = ipaddress.ip_network(trusted, strict=False)
                        if ip_obj in network:
                            return True
                    else:
                        # Handle single IP
                        if ip_obj == ipaddress.ip_address(trusted):
                            return True
                except (ipaddress.AddressValueError, ValueError):
                    continue
            return False
        except (ipaddress.AddressValueError, ValueError):
            return False

    # Only trust proxy headers if request comes from trusted proxy
    if not is_trusted_proxy(direct_ip):
        return direct_ip

    # Check X-Forwarded-For header (most common)
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The leftmost is typically the original client
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        for ip in ips:
            if ip and not is_trusted_proxy(ip):
                # First non-proxy IP is likely the real client
                try:
                    ipaddress.ip_address(ip)  # Validate IP format
                    return ip
                except (ipaddress.AddressValueError, ValueError):
                    continue

    # Check X-Real-IP header (Nginx style)
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        try:
            ipaddress.ip_address(real_ip)  # Validate IP format
            return real_ip
        except (ipaddress.AddressValueError, ValueError):
            pass

    # Check X-Forwarded header (RFC 7239 style)
    forwarded = request.headers.get("forwarded", "")
    if forwarded:
        # Parse Forwarded header: for=192.0.2.60;proto=http;by=203.0.113.43
        for part in forwarded.split(";"):
            if part.strip().startswith("for="):
                ip = part.split("=", 1)[1].strip().strip('"')
                # Remove port if present (IPv4:port or [IPv6]:port)
                if ":" in ip and not ip.startswith("["):
                    ip = ip.split(":", 1)[0]
                elif ip.startswith("[") and "]:" in ip:
                    ip = ip[1 : ip.index("]:")]
                try:
                    ipaddress.ip_address(ip)  # Validate IP format
                    if not is_trusted_proxy(ip):
                        return ip
                except (ipaddress.AddressValueError, ValueError):
                    continue

    # If all proxy headers are invalid or missing, return direct connection IP
    return direct_ip


def generate_device_fingerprint(
    request: "Request", trusted_proxies: list[str] | None = None
) -> str:
    """
    Generate a device fingerprint from request headers.

    Security considerations:
    - Balances security (session binding) with privacy
    - Uses only standard headers to avoid fingerprinting concerns
    - Hash ensures consistent format and prevents header injection
    - Properly handles real client IP through proxy headers

    Args:
        request: The incoming HTTP request
        trusted_proxies: List of trusted proxy IPs for X-Forwarded-For handling

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

    # Include real client IP for additional security (with proxy support)
    client_ip = get_client_ip(request, trusted_proxies)
    fingerprint_data["client_ip"] = client_ip

    # Create deterministic string representation
    fingerprint_string = "|".join(
        [f"{k}:{v}" for k, v in sorted(fingerprint_data.items())]
    )

    # Hash to create consistent, privacy-conscious fingerprint
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()


def sanitize_user_input(value: str, max_length: int = 1000) -> str:
    """
    Sanitize user input for logging and storage using bleach.

    Security considerations:
    - Uses battle-tested bleach library for sanitization
    - Prevents injection attacks in logs
    - Limits input length to prevent DoS
    - Removes dangerous characters and sequences

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
        value = value[:max_length] + "...[TRUNCATED]"

    try:
        import bleach

        # Use bleach to clean the input for safe logging/storage
        # Strip all HTML tags and attributes, but keep text content
        sanitized = bleach.clean(
            value,
            tags=[],  # No tags allowed
            attributes={},  # No attributes allowed
            strip=True,  # Strip tags rather than escape them
            strip_comments=True,  # Remove HTML comments
        )

        # Additional log injection prevention: make CRLF visible
        sanitized = sanitized.replace("\r", "\\r").replace("\n", "\\n")

        return sanitized

    except ImportError:
        # Fallback if bleach is not available (basic sanitization)
        # This should not happen in production with proper dependencies
        sanitized = ""
        for char in value:
            if char == "\0":  # Remove null bytes
                continue
            elif char in "\r\n":  # Make CRLF visible to prevent log injection
                sanitized += "\\n"
            elif char == "\t" or char.isprintable():  # Keep tabs and printable chars
                sanitized += char
            # Skip other control characters

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
    Timing-safe string comparison using cryptography library.

    Security considerations:
    - Prevents timing attacks on string comparisons
    - Uses cryptographically secure constant-time comparison
    - Critical for comparing tokens, hashes, etc.

    Args:
        a: First string to compare
        b: Second string to compare

    Returns:
        True if strings are equal
    """
    from cryptography.hazmat.primitives import constant_time

    # Pad strings to same length to avoid length-based timing attacks
    max_len = max(len(a), len(b))
    a_padded = a.ljust(max_len, "\0")
    b_padded = b.ljust(max_len, "\0")

    return constant_time.bytes_eq(a_padded.encode("utf-8"), b_padded.encode("utf-8"))


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
            if isinstance(value, dict):
                # Recursively mask nested dictionaries even for sensitive keys
                masked[key] = mask_sensitive_data(value)
            elif isinstance(value, str) and len(value) > 4:
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


def get_common_trusted_proxies() -> dict[str, list[str]]:
    """
    Get commonly used trusted proxy configurations.

    Returns:
        Dictionary of common proxy configurations for easy setup
    """
    return {
        # Common cloud provider load balancers
        "aws_alb": [
            "10.0.0.0/8",  # AWS VPC private ranges
            "172.16.0.0/12",  # AWS VPC private ranges
            "192.168.0.0/16",  # AWS VPC private ranges
        ],
        "cloudflare": [
            # Cloudflare IP ranges (these change, check Cloudflare docs)
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18",
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22",
        ],
        "google_cloud": [
            "10.0.0.0/8",  # GCP private ranges
            "172.16.0.0/12",  # GCP private ranges
            "192.168.0.0/16",  # GCP private ranges
        ],
        "azure": [
            "10.0.0.0/8",  # Azure private ranges
            "172.16.0.0/12",  # Azure private ranges
            "192.168.0.0/16",  # Azure private ranges
        ],
        # Common reverse proxy setups
        "nginx_local": ["127.0.0.1", "::1"],
        "docker_bridge": ["172.17.0.0/16"],
        "kubernetes": ["10.0.0.0/8"],
        # Common private networks
        "rfc1918": [
            "10.0.0.0/8",  # Class A private
            "172.16.0.0/12",  # Class B private
            "192.168.0.0/16",  # Class C private
        ],
    }


def configure_trusted_proxies(
    proxy_config: str | list[str] | None = None,
    additional_proxies: list[str] | None = None,
) -> list[str]:
    """
    Configure trusted proxies with common presets and custom additions.

    Args:
        proxy_config: Either a preset name, list of IPs/CIDRs, or None
        additional_proxies: Additional proxy IPs to trust

    Returns:
        List of trusted proxy IPs/CIDRs

    Examples:
        # Use common preset
        configure_trusted_proxies("cloudflare")

        # Use custom list
        configure_trusted_proxies(["10.0.0.1", "192.168.1.0/24"])

        # Combine preset with additional
        configure_trusted_proxies("aws_alb", ["203.0.113.1"])
    """
    trusted_proxies = []

    if proxy_config:
        if isinstance(proxy_config, str):
            # Use preset configuration
            presets = get_common_trusted_proxies()
            if proxy_config in presets:
                trusted_proxies.extend(presets[proxy_config])
            else:
                raise ValueError(
                    f"Unknown proxy preset: {proxy_config}. Available: {list(presets.keys())}"
                )
        elif isinstance(proxy_config, list):
            # Use custom list
            trusted_proxies.extend(proxy_config)
        else:
            raise ValueError("proxy_config must be a string preset name or list of IPs")

    if additional_proxies:
        trusted_proxies.extend(additional_proxies)

    return trusted_proxies
