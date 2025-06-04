"""
RateLimiter interface for the Serv authentication framework.

This module defines the abstract base class for rate limiting,
providing protection against brute force attacks and DoS attempts.

Security considerations:
- Rate limiting must be reliable and not bypassable
- Limits should be configurable per action and identifier
- Rate limit storage must be efficient and accurate
- Rate limit responses should not leak information
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from .types import RateLimitResult


class RateLimiter(ABC):
    """
    Abstract base class for rate limiting services.

    Rate limiters protect against brute force attacks, DoS attempts,
    and abuse by limiting the rate of requests from specific identifiers
    (IP addresses, user accounts, etc.) for specific actions.

    Security requirements:
    - Rate limits MUST be enforced reliably
    - Rate limit checks MUST be fast (< 1ms)
    - Rate limit storage MUST be accurate
    - Rate limit responses MUST not leak information
    - Rate limits SHOULD be configurable per action

    All implementations should be stateless and use dependency injection
    for storage and configuration services.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the rate limiter.

        Args:
            config: Rate limiter configuration
        """
        self.config = config.copy()  # Defensive copy
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate rate limiter configuration.

        Should validate rate limit rules, storage configuration,
        and performance settings.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def check_limit(self, identifier: str, action: str) -> RateLimitResult:
        """
        Check if request is within rate limit.

        Checks the current rate limit status for the identifier/action
        combination without consuming a request. Use this to check
        limits before performing expensive operations.

        Security requirements:
        - MUST be fast and efficient (< 1ms typical)
        - MUST return accurate limit information
        - MUST NOT leak information about other identifiers
        - SHOULD handle storage failures gracefully

        Args:
            identifier: Unique identifier for rate limiting (IP, user ID, etc.)
            action: Action being rate limited ("login", "api_request", etc.)

        Returns:
            RateLimitResult with current limit status

        Example:
            ```python
            async def check_limit(self, identifier: str, action: str) -> RateLimitResult:
                # Get rate limit configuration for action
                limit_config = self._get_limit_config(action)
                if not limit_config:
                    # No limit configured - allow
                    return RateLimitResult(
                        allowed=True,
                        limit=float('inf'),
                        remaining=float('inf'),
                        reset_time=datetime.now(timezone.utc)
                    )

                # Get current usage from storage
                usage = await self._get_usage(identifier, action)

                # Calculate remaining quota
                remaining = max(0, limit_config["limit"] - usage["count"])

                return RateLimitResult(
                    allowed=remaining > 0,
                    limit=limit_config["limit"],
                    remaining=remaining,
                    reset_time=usage["reset_time"],
                    retry_after=usage.get("retry_after")
                )
            ```
        """
        pass

    @abstractmethod
    async def track_attempt(self, identifier: str, action: str) -> RateLimitResult:
        """
        Track an attempt and return updated rate limit status.

        Records the attempt and returns the updated rate limit status.
        This is the primary method used during request processing.

        Security requirements:
        - MUST atomically check and update limits
        - MUST be accurate under concurrency
        - MUST handle storage failures gracefully
        - SHOULD be efficient for high load

        Args:
            identifier: Unique identifier for rate limiting
            action: Action being performed

        Returns:
            RateLimitResult with updated limit status

        Example:
            ```python
            async def track_attempt(self, identifier: str, action: str) -> RateLimitResult:
                # Get rate limit configuration
                limit_config = self._get_limit_config(action)
                if not limit_config:
                    # No limit configured
                    return RateLimitResult(
                        allowed=True,
                        limit=float('inf'),
                        remaining=float('inf'),
                        reset_time=datetime.now(timezone.utc)
                    )

                # Atomically check and update usage
                usage = await self._check_and_update_usage(
                    identifier,
                    action,
                    limit_config
                )

                # Calculate result
                allowed = usage["count"] <= limit_config["limit"]
                remaining = max(0, limit_config["limit"] - usage["count"])

                result = RateLimitResult(
                    allowed=allowed,
                    limit=limit_config["limit"],
                    remaining=remaining,
                    reset_time=usage["reset_time"]
                )

                # Add retry-after if blocked
                if not allowed:
                    result.retry_after = self._calculate_retry_after(usage)

                return result
            ```
        """
        pass

    @abstractmethod
    async def reset_limits(self, identifier: str, action: str | None = None) -> None:
        """
        Reset rate limits for an identifier.

        Clears rate limit counters for the identifier. If action is
        specified, only that action is reset. Otherwise, all actions
        for the identifier are reset.

        Security requirements:
        - MUST completely clear rate limit state
        - SHOULD emit audit event
        - SHOULD be used sparingly

        Args:
            identifier: Identifier to reset
            action: Specific action to reset (None for all actions)

        Example:
            ```python
            async def reset_limits(self, identifier: str, action: Optional[str] = None) -> None:
                if action:
                    # Reset specific action
                    await self._clear_usage(identifier, action)
                    await self._emit_reset_event("action_reset", identifier, action)
                else:
                    # Reset all actions for identifier
                    await self._clear_all_usage(identifier)
                    await self._emit_reset_event("identifier_reset", identifier)
            ```
        """
        pass

    async def get_limit_info(self, action: str) -> dict[str, Any]:
        """
        Get rate limit configuration for an action.

        Returns the configured rate limits for the specified action.
        Useful for API documentation and client guidance.

        Args:
            action: Action to get limits for

        Returns:
            Dictionary with limit configuration
        """
        # Default implementation - providers should override
        return {}

    async def get_top_offenders(
        self, action: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get identifiers with highest usage for an action.

        Used for monitoring and security analysis.
        Returns list of identifiers sorted by usage.

        Args:
            action: Action to analyze
            limit: Maximum number of results

        Returns:
            List of usage information for top identifiers
        """
        # Default implementation - providers should override
        return []

    def _parse_limit_string(self, limit_str: str) -> dict[str, Any]:
        """
        Parse rate limit string like "10/min" or "100/hour".

        Args:
            limit_str: Limit string to parse

        Returns:
            Dictionary with limit and window information

        Raises:
            ValueError: If limit string is invalid
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

            return {
                "limit": count,
                "window_seconds": window_seconds,
                "window_name": window_str.lower(),
            }

        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid rate limit format '{limit_str}': {e}") from e

    def _get_limit_config(self, action: str) -> dict[str, Any] | None:
        """
        Get rate limit configuration for an action.

        Args:
            action: Action name

        Returns:
            Limit configuration or None if no limit
        """
        # Check action-specific config
        action_config = self.config.get("limits", {}).get(action)
        if action_config:
            if isinstance(action_config, str):
                return self._parse_limit_string(action_config)
            return action_config

        # Check default config
        default_config = self.config.get("default_limit")
        if default_config:
            if isinstance(default_config, str):
                return self._parse_limit_string(default_config)
            return default_config

        return None

    def _calculate_retry_after(self, usage: dict[str, Any]) -> int:
        """
        Calculate retry-after seconds based on usage.

        Args:
            usage: Usage information

        Returns:
            Seconds until next attempt allowed
        """
        reset_time = usage.get("reset_time")
        if not reset_time:
            return 60  # Default 1 minute

        now = datetime.now(UTC)
        if reset_time <= now:
            return 0

        return int((reset_time - now).total_seconds())

    async def cleanup_expired_limits(self) -> int:
        """
        Clean up expired rate limit data.

        Removes expired rate limit counters to maintain storage hygiene.
        Should be called periodically by a background task.

        Returns:
            Number of expired entries cleaned up
        """
        # Default implementation - providers should override
        return 0

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when rate limiter is being shut down.

        Override this method to cleanup any resources (connections,
        caches, timers, etc.) when the rate limiter is being destroyed.
        """
        pass
