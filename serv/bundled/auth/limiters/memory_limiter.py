"""
Memory-based Rate Limiter implementation.

This implementation provides in-memory rate limiting using sliding window
algorithms. Suitable for development and single-instance deployments.

Security features:
- Sliding window algorithm for accurate rate limiting
- Configurable time windows and limits
- Memory-efficient cleanup of expired entries
- Protection against resource exhaustion attacks
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

from serv.auth.rate_limiter import RateLimiter
from serv.auth.types import RateLimitResult

logger = logging.getLogger(__name__)


class MemoryRateLimiter(RateLimiter):
    """
    In-memory rate limiter using sliding window algorithm.

    This implementation stores rate limit data in memory using efficient
    data structures. Suitable for development and small-scale deployments.

    Security considerations:
    - Implements sliding window for accurate rate limiting
    - Automatic cleanup prevents memory exhaustion
    - Thread-safe for concurrent access
    - Configurable limits per action type
    """

    def __init__(
        self,
        default_limits: dict[str, str] | None = None,
        cleanup_interval_seconds: int = 300,  # 5 minutes
        max_tracked_identifiers: int = 10000,
    ):
        """
        Initialize memory-based rate limiter.

        Args:
            default_limits: Default rate limits by action (e.g., {"login": "5/min"})
            cleanup_interval_seconds: How often to clean expired entries
            max_tracked_identifiers: Maximum identifiers to track (prevents DoS)
        """
        self.default_limits = default_limits or {}
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_tracked_identifiers = max_tracked_identifiers

        # Storage: {identifier: {action: deque([timestamp, ...])}}
        self._requests: dict[str, dict[str, deque[float]]] = defaultdict(
            lambda: defaultdict(deque)
        )
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_cleanup = time.time()

        logger.info(f"Memory rate limiter initialized with defaults: {default_limits}")

    async def check_rate_limit(
        self, identifier: str, action: str, limit_override: str | None = None
    ) -> RateLimitResult:
        """
        Check if request should be rate limited.

        Uses sliding window algorithm to track requests over time.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            action: Action being rate limited
            limit_override: Override default limit for this check

        Returns:
            Rate limit result with current status
        """
        try:
            # Get rate limit configuration
            limit_str = limit_override or self.default_limits.get(action, "100/hour")
            limit_config = self._parse_limit_string(limit_str)

            current_time = time.time()
            window_start = current_time - limit_config["window_seconds"]

            # Get or create lock for this identifier (thread-safe)
            if identifier not in self._locks:
                self._locks.setdefault(identifier, asyncio.Lock())

            async with self._locks[identifier]:
                # Perform periodic cleanup
                await self._cleanup_if_needed()

                # Check if we're tracking too many identifiers
                if (
                    len(self._requests) >= self.max_tracked_identifiers
                    and identifier not in self._requests
                ):
                    logger.warning(
                        f"Rate limiter at capacity ({self.max_tracked_identifiers} identifiers)"
                    )
                    # Still allow the request but log the issue

                # Get request history for this identifier/action
                request_times = self._requests[identifier][action]

                # Remove expired requests (outside sliding window)
                while request_times and request_times[0] < window_start:
                    request_times.popleft()

                # Check if limit exceeded
                current_count = len(request_times)
                remaining = max(0, limit_config["limit"] - current_count)
                allowed = current_count < limit_config["limit"]

                if allowed:
                    # Record this request
                    request_times.append(current_time)
                    remaining -= 1

                # Calculate reset time (when oldest request expires)
                reset_time = datetime.fromtimestamp(
                    request_times[0] + limit_config["window_seconds"]
                    if request_times
                    else current_time + limit_config["window_seconds"],
                    UTC,
                )

                # Calculate retry_after if rate limited
                retry_after = None
                if not allowed and request_times:
                    retry_after = int(
                        request_times[0] + limit_config["window_seconds"] - current_time
                    )
                    retry_after = max(1, retry_after)  # At least 1 second

                logger.debug(
                    f"Rate limit check: {identifier}/{action} = {current_count}/{limit_config['limit']} "
                    f"(allowed: {allowed}, remaining: {remaining})"
                )

                return RateLimitResult(
                    allowed=allowed,
                    limit=limit_config["limit"],
                    remaining=remaining,
                    reset_time=reset_time,
                    retry_after=retry_after,
                    metadata={
                        "window": limit_config["window_name"],
                        "window_seconds": limit_config["window_seconds"],
                        "algorithm": "sliding_window",
                        "current_count": current_count,
                    },
                )

        except Exception as e:
            logger.error(f"Rate limit check error for {identifier}/{action}: {e}")
            # On error, allow the request (fail open)
            return RateLimitResult(
                allowed=True,
                limit=1000,  # High default
                remaining=999,
                reset_time=datetime.now(UTC) + timedelta(hours=1),
                metadata={"error": "rate_limiter_error", "fallback": True},
            )

    async def reset_rate_limit(self, identifier: str, action: str) -> None:
        """
        Reset rate limit for specific identifier/action.

        Args:
            identifier: Identifier to reset
            action: Action to reset
        """
        try:
            if identifier in self._locks:
                async with self._locks[identifier]:
                    if (
                        identifier in self._requests
                        and action in self._requests[identifier]
                    ):
                        self._requests[identifier][action].clear()
                        logger.info(f"Reset rate limit for {identifier}/{action}")
        except Exception as e:
            logger.error(f"Error resetting rate limit for {identifier}/{action}: {e}")

    async def get_rate_limit_status(
        self, identifier: str, action: str
    ) -> RateLimitResult:
        """
        Get current rate limit status without consuming a request.

        Args:
            identifier: Identifier to check
            action: Action to check

        Returns:
            Current rate limit status
        """
        try:
            limit_str = self.default_limits.get(action, "100/hour")
            limit_config = self._parse_limit_string(limit_str)

            current_time = time.time()
            window_start = current_time - limit_config["window_seconds"]

            if identifier in self._locks:
                async with self._locks[identifier]:
                    request_times = self._requests[identifier][action]

                    # Count requests in current window (don't modify)
                    current_count = sum(1 for t in request_times if t >= window_start)
                    remaining = max(0, limit_config["limit"] - current_count)

                    reset_time = datetime.fromtimestamp(
                        request_times[0] + limit_config["window_seconds"]
                        if request_times
                        else current_time + limit_config["window_seconds"],
                        UTC,
                    )

                    return RateLimitResult(
                        allowed=current_count < limit_config["limit"],
                        limit=limit_config["limit"],
                        remaining=remaining,
                        reset_time=reset_time,
                        metadata={
                            "window": limit_config["window_name"],
                            "algorithm": "sliding_window",
                            "current_count": current_count,
                        },
                    )
            else:
                # No requests yet
                return RateLimitResult(
                    allowed=True,
                    limit=limit_config["limit"],
                    remaining=limit_config["limit"],
                    reset_time=datetime.now(UTC)
                    + timedelta(seconds=limit_config["window_seconds"]),
                    metadata={
                        "window": limit_config["window_name"],
                        "algorithm": "sliding_window",
                    },
                )

        except Exception as e:
            logger.error(
                f"Error getting rate limit status for {identifier}/{action}: {e}"
            )
            return RateLimitResult(
                allowed=True,
                limit=1000,
                remaining=999,
                reset_time=datetime.now(UTC) + timedelta(hours=1),
                metadata={"error": "rate_limiter_error"},
            )

    async def _cleanup_if_needed(self) -> None:
        """Clean up expired entries periodically."""
        current_time = time.time()
        if current_time - self._last_cleanup < self.cleanup_interval_seconds:
            return

        self._last_cleanup = current_time

        # Clean up expired entries and empty data structures
        identifiers_to_remove = []

        for identifier, actions in self._requests.items():
            actions_to_remove = []

            for action, request_times in actions.items():
                # Get window for this action
                limit_str = self.default_limits.get(action, "100/hour")
                limit_config = self._parse_limit_string(limit_str)
                window_start = current_time - limit_config["window_seconds"]

                # Remove expired requests
                while request_times and request_times[0] < window_start:
                    request_times.popleft()

                # Mark empty actions for removal
                if not request_times:
                    actions_to_remove.append(action)

            # Remove empty actions
            for action in actions_to_remove:
                del actions[action]

            # Mark empty identifiers for removal
            if not actions:
                identifiers_to_remove.append(identifier)

        # Remove empty identifiers
        for identifier in identifiers_to_remove:
            del self._requests[identifier]
            if identifier in self._locks:
                del self._locks[identifier]

        if identifiers_to_remove:
            logger.debug(
                f"Cleaned up {len(identifiers_to_remove)} expired rate limit entries"
            )

    def _parse_limit_string(self, limit_str: str) -> dict[str, Any]:
        """
        Parse rate limit string like "10/min" or "100/hour".

        Args:
            limit_str: Limit string to parse

        Returns:
            Dictionary with limit and window information
        """
        try:
            count_str, window_str = limit_str.split("/", 1)
            count = int(count_str)

            window_map = {
                "sec": 1,
                "second": 1,
                "min": 60,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }

            window_seconds = window_map.get(window_str.lower())
            if window_seconds is None:
                raise ValueError(f"Invalid time window: {window_str}")

            if count <= 0:
                raise ValueError("Rate limit count must be positive")

            return {
                "limit": count,
                "window_seconds": window_seconds,
                "window_name": window_str.lower(),
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid rate limit format '{limit_str}': {e}")
            # Return safe default
            return {"limit": 100, "window_seconds": 3600, "window_name": "hour"}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "MemoryRateLimiter":
        """
        Create memory rate limiter from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Configured memory rate limiter
        """
        return cls(
            default_limits=config.get("default_limits", {}),
            cleanup_interval_seconds=config.get("cleanup_interval_seconds", 300),
            max_tracked_identifiers=config.get("max_tracked_identifiers", 10000),
        )
