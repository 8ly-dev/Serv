"""
Timing attack security tests.

These tests verify that the authentication system is protected against
timing-based information disclosure attacks.

⚠️  WARNING: These tests simulate real timing attack scenarios.
"""

import asyncio
import statistics
import time

import pytest

from serv.auth.utils import MinimumRuntime, secure_compare, timing_protection


class TestTimingAttackProtection:
    """Test protection against timing attacks."""

    @pytest.mark.asyncio
    async def test_minimum_runtime_enforced(self):
        """Test that MinimumRuntime enforces minimum execution time."""
        minimum_time = 0.1  # 100ms

        start_time = time.perf_counter()
        async with MinimumRuntime(minimum_time):
            # Fast operation that would normally complete in microseconds
            await asyncio.sleep(0.001)  # 1ms
        end_time = time.perf_counter()

        elapsed = end_time - start_time
        assert elapsed >= minimum_time, f"Expected >= {minimum_time}s, got {elapsed}s"
        assert elapsed < minimum_time + 0.05, (
            f"Should not exceed minimum by much, got {elapsed}s"
        )

    @pytest.mark.asyncio
    async def test_timing_protection_context_manager(self):
        """Test timing_protection context manager."""
        minimum_time = 0.05  # 50ms

        # Test fast operation
        start_time = time.perf_counter()
        async with timing_protection(minimum_time):
            pass  # Instant operation
        fast_elapsed = time.perf_counter() - start_time

        # Test slow operation
        start_time = time.perf_counter()
        async with timing_protection(minimum_time):
            await asyncio.sleep(minimum_time + 0.01)  # Longer than minimum
        slow_elapsed = time.perf_counter() - start_time

        # Both should take at least the minimum time
        assert fast_elapsed >= minimum_time
        assert slow_elapsed >= minimum_time + 0.01

    @pytest.mark.asyncio
    async def test_timing_consistency_across_operations(self):
        """Test that different operations take consistent time."""
        minimum_time = 0.1
        times = []

        # Run multiple operations of varying complexity
        operations = [
            lambda: asyncio.sleep(0.001),  # Fast
            lambda: asyncio.sleep(0.005),  # Medium
            lambda: asyncio.sleep(0.02),  # Slow (but less than minimum)
        ]

        for operation in operations:
            for _ in range(3):  # Run each operation multiple times
                start_time = time.perf_counter()
                async with timing_protection(minimum_time):
                    await operation()
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

        # All operations should take approximately the same time
        mean_time = statistics.mean(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0

        assert all(t >= minimum_time for t in times), (
            "All operations should meet minimum time"
        )
        assert std_dev < 0.02, (
            f"Standard deviation too high: {std_dev}s (times: {times})"
        )

    def test_secure_compare_timing_consistency(self):
        """Test that secure_compare takes consistent time regardless of input."""
        # Test strings of same length but different content
        test_cases = [
            ("password123", "password123"),  # Identical
            ("password123", "password456"),  # Different at end
            ("password123", "different123"),  # Different at start
            ("password123", "pqssword123"),  # Different in middle
            ("aaaaaaaaaaa", "bbbbbbbbbbb"),  # Completely different
        ]

        times = []
        for a, b in test_cases:
            # Run comparison multiple times
            for _ in range(100):
                start_time = time.perf_counter()
                result = secure_compare(a, b)
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

                # Verify correctness
                if a == b:
                    assert result is True
                else:
                    assert result is False

        # Check timing consistency
        if len(times) > 1:
            mean_time = statistics.mean(times)
            std_dev = statistics.stdev(times)

            # Standard deviation should be small relative to mean
            # (allowing for some variation due to system scheduling)
            relative_std = std_dev / mean_time if mean_time > 0 else 0
            assert relative_std < 0.5, (
                f"Timing too variable: {relative_std:.3f} (mean: {mean_time:.6f}s, std: {std_dev:.6f}s)"
            )

    def test_secure_compare_different_lengths(self):
        """Test secure_compare with different length strings."""
        # Different length strings should return False quickly but consistently
        test_cases = [
            ("short", "verylongstring"),
            ("a", "bb"),
            ("", "nonempty"),
            ("medium", "med"),
        ]

        times = []
        for a, b in test_cases:
            for _ in range(50):
                start_time = time.perf_counter()
                result = secure_compare(a, b)
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

                assert result is False  # Different lengths should always be False

        # Even different length comparisons should have consistent timing
        if len(times) > 1:
            std_dev = statistics.stdev(times)
            mean_time = statistics.mean(times)
            relative_std = std_dev / mean_time if mean_time > 0 else 0
            assert relative_std < 0.5, (
                f"Different length timing too variable: {relative_std:.3f}"
            )

    @pytest.mark.asyncio
    async def test_authentication_timing_protection_simulation(
        self, mock_auth_provider
    ):
        """Test timing protection in authentication scenarios."""
        minimum_time = 0.1

        # Simulate authentication attempts that would normally have different timings
        test_scenarios = [
            {"username": "valid_user", "password": "correct_password"},  # Valid
            {"username": "valid_user", "password": "wrong_password"},  # Wrong password
            {"username": "nonexistent", "password": "any_password"},  # Wrong username
            {"username": "", "password": ""},  # Empty credentials
            {"username": "a" * 1000, "password": "b" * 1000},  # Long inputs
        ]

        times = []
        for scenario in test_scenarios:
            start_time = time.perf_counter()
            async with timing_protection(minimum_time):
                await mock_auth_provider.initiate_auth(scenario)
            elapsed = time.perf_counter() - start_time
            times.append(elapsed)

        # All authentication attempts should take approximately the same time
        assert all(t >= minimum_time for t in times), (
            "All auth attempts should meet minimum time"
        )

        if len(times) > 1:
            mean_time = statistics.mean(times)
            std_dev = statistics.stdev(times)
            relative_std = std_dev / mean_time if mean_time > 0 else 0
            assert relative_std < 0.1, f"Auth timing too variable: {relative_std:.3f}"

    @pytest.mark.asyncio
    async def test_exception_handling_preserves_timing(self):
        """Test that exceptions don't break timing protection."""
        minimum_time = 0.1

        async def failing_operation():
            await asyncio.sleep(0.001)  # Fast operation
            raise ValueError("Simulated error")

        # Exception should not prevent timing protection
        start_time = time.perf_counter()
        with pytest.raises(ValueError):
            async with timing_protection(minimum_time):
                await failing_operation()
        elapsed = time.perf_counter() - start_time

        assert elapsed >= minimum_time, (
            f"Exception broke timing protection: {elapsed}s < {minimum_time}s"
        )

    def test_minimum_runtime_validation(self):
        """Test MinimumRuntime input validation."""
        # Should reject negative or zero values
        with pytest.raises(ValueError, match="Minimum runtime must be positive"):
            MinimumRuntime(0)

        with pytest.raises(ValueError, match="Minimum runtime must be positive"):
            MinimumRuntime(-0.1)

        # Should accept positive values
        runtime = MinimumRuntime(0.1)
        assert runtime.minimum_seconds == 0.1


class TestTimingAttackVulnerabilityDetection:
    """Tests designed to detect potential timing attack vulnerabilities."""

    def test_string_operations_timing_safety(self):
        """Test that string operations don't leak timing information."""
        # Test various string operations that might be vulnerable
        base_string = "secret_password_123"

        # Test different positions of differences
        test_strings = [
            "secret_password_123",  # Identical
            "xecret_password_123",  # Different at position 0
            "sexret_password_123",  # Different at position 2
            "secret_passworg_123",  # Different in middle
            "secret_password_12x",  # Different at end
            "completely_different",  # Completely different
        ]

        timing_results = {}

        for test_string in test_strings:
            times = []
            for _ in range(100):
                start = time.perf_counter()
                # Use secure_compare instead of ==
                result = secure_compare(base_string, test_string)
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            timing_results[test_string] = {
                "mean": statistics.mean(times),
                "std": statistics.stdev(times) if len(times) > 1 else 0,
                "result": result,
            }

        # Verify that timing doesn't correlate with string similarity
        means = [data["mean"] for data in timing_results.values()]
        overall_std = statistics.stdev(means) if len(means) > 1 else 0
        overall_mean = statistics.mean(means)

        # Relative standard deviation should be small
        relative_std = overall_std / overall_mean if overall_mean > 0 else 0
        assert relative_std < 0.3, (
            f"String comparison timing varies too much: {relative_std:.3f}"
        )

    @pytest.mark.asyncio
    async def test_user_enumeration_timing_protection(self, mock_auth_provider):
        """Test that user enumeration is protected by timing consistency."""
        # These scenarios might have different timings in vulnerable implementations
        scenarios = [
            {
                "username": "valid_user",
                "password": "wrong",
            },  # Valid user, wrong password
            {
                "username": "nonexistent",
                "password": "wrong",
            },  # Invalid user, wrong password
            {"username": "", "password": "wrong"},  # Empty user, wrong password
            {
                "username": "admin",
                "password": "wrong",
            },  # Common username, wrong password
            {"username": "test", "password": "wrong"},  # Short username, wrong password
            {
                "username": "very_long_username_that_does_not_exist",
                "password": "wrong",
            },  # Long invalid username
        ]

        timing_data = []
        for scenario in scenarios:
            times = []
            for _ in range(10):  # Multiple attempts per scenario
                start_time = time.perf_counter()
                async with timing_protection(0.1):  # Use timing protection
                    await mock_auth_provider.initiate_auth(scenario)
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

            timing_data.append(
                {
                    "scenario": scenario["username"],
                    "mean": statistics.mean(times),
                    "std": statistics.stdev(times) if len(times) > 1 else 0,
                }
            )

        # All scenarios should have similar timing
        means = [data["mean"] for data in timing_data]
        overall_std = statistics.stdev(means) if len(means) > 1 else 0
        overall_mean = statistics.mean(means)

        relative_std = overall_std / overall_mean if overall_mean > 0 else 0
        assert relative_std < 0.1, (
            f"User enumeration timing attack possible: {relative_std:.3f}"
        )

    def test_password_length_timing_independence(self):
        """Test that password validation timing doesn't depend on password length."""
        base_password = "correct_password"

        # Test passwords of different lengths
        test_passwords = [
            "a",  # Very short
            "short",  # Short
            "medium_password",  # Medium
            "this_is_a_very_long_password_that_should_not_affect_timing",  # Very long
            base_password,  # Correct length
        ]

        timing_results = []
        for password in test_passwords:
            times = []
            for _ in range(50):
                start = time.perf_counter()
                # Simulate password validation with consistent timing
                result = secure_compare(base_password, password)
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            timing_results.append(
                {
                    "password_length": len(password),
                    "mean_time": statistics.mean(times),
                    "correct": password == base_password,
                }
            )

        # Timing should not correlate with password length
        lengths = [r["password_length"] for r in timing_results]
        times = [r["mean_time"] for r in timing_results]

        # Calculate correlation coefficient
        if len(lengths) > 2:
            mean_length = statistics.mean(lengths)
            mean_time = statistics.mean(times)

            numerator = sum(
                (l - mean_length) * (t - mean_time) for l, t in zip(lengths, times, strict=False)
            )
            denominator = (
                sum((l - mean_length) ** 2 for l in lengths)
                * sum((t - mean_time) ** 2 for t in times)
            ) ** 0.5

            correlation = numerator / denominator if denominator > 0 else 0

            # Correlation should be close to zero (no relationship between length and time)
            assert abs(correlation) < 0.5, (
                f"Timing correlates with password length: {correlation:.3f}"
            )
