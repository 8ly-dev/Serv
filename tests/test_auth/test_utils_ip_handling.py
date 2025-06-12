"""
Tests for IP handling and X-Forwarded-For support in auth utils.

These tests verify that the client IP extraction works correctly and securely
with various proxy configurations and potential attack scenarios.
"""

from unittest.mock import Mock

import pytest

from serv.auth.utils import get_client_ip, generate_device_fingerprint, configure_trusted_proxies, get_common_trusted_proxies


class TestGetClientIP:
    """Test secure client IP extraction with proxy support."""

    def create_mock_request(self, client_host="127.0.0.1", headers=None):
        """Create a mock request with specified client and headers."""
        request = Mock()
        request.client = Mock()
        request.client.host = client_host
        request.headers = Mock()
        
        # Set up headers.get() method
        headers = headers or {}
        def get_header(key, default=""):
            return headers.get(key.lower(), default)
        
        request.headers.get = get_header
        return request

    def test_direct_connection_no_proxies(self):
        """Test direct connection without any proxy configuration."""
        request = self.create_mock_request("192.168.1.100")
        
        # No trusted proxies - should return direct IP
        result = get_client_ip(request)
        assert result == "192.168.1.100"
        
        # Empty trusted proxies list - should return direct IP
        result = get_client_ip(request, [])
        assert result == "192.168.1.100"

    def test_direct_connection_with_untrusted_headers(self):
        """Test that untrusted proxy headers are ignored."""
        headers = {
            "x-forwarded-for": "10.0.0.1, 203.0.113.1",
            "x-real-ip": "10.0.0.2",
        }
        request = self.create_mock_request("192.168.1.100", headers)
        
        # No trusted proxies configured - headers should be ignored
        result = get_client_ip(request)
        assert result == "192.168.1.100"

    def test_trusted_proxy_x_forwarded_for(self):
        """Test X-Forwarded-For header from trusted proxy."""
        headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.1, 10.0.0.2"}
        request = self.create_mock_request("10.0.0.1", headers)
        
        # Trust the proxy we're connecting from
        trusted_proxies = ["10.0.0.1", "10.0.0.2"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should return the leftmost non-proxy IP
        assert result == "203.0.113.1"

    def test_trusted_proxy_x_real_ip(self):
        """Test X-Real-IP header from trusted proxy."""
        headers = {"x-real-ip": "203.0.113.1"}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "203.0.113.1"

    def test_trusted_proxy_forwarded_header(self):
        """Test RFC 7239 Forwarded header from trusted proxy."""
        headers = {"forwarded": 'for=203.0.113.1;proto=https;by=10.0.0.1'}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "203.0.113.1"

    def test_trusted_proxy_forwarded_header_with_port(self):
        """Test Forwarded header with port information."""
        headers = {"forwarded": 'for="203.0.113.1:8080";proto=https'}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "203.0.113.1"

    def test_trusted_proxy_forwarded_header_ipv6(self):
        """Test Forwarded header with IPv6 address."""
        headers = {"forwarded": 'for="[2001:db8::1]:8080";proto=https'}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "2001:db8::1"

    def test_cidr_trusted_proxy(self):
        """Test CIDR notation for trusted proxy networks."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("10.0.0.5", headers)
        
        # Trust entire 10.0.0.0/24 network
        trusted_proxies = ["10.0.0.0/24"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "203.0.113.1"

    def test_untrusted_proxy_source(self):
        """Test that headers from untrusted sources are ignored."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("192.168.1.100", headers)
        
        # Only trust 10.0.0.0/8 network
        trusted_proxies = ["10.0.0.0/8"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should return direct IP since 192.168.1.100 is not trusted
        assert result == "192.168.1.100"

    def test_multiple_proxy_chain(self):
        """Test handling of multiple proxies in chain."""
        headers = {"x-forwarded-for": "203.0.113.1, 10.0.0.1, 10.0.0.2"}
        request = self.create_mock_request("10.0.0.2", headers)
        
        # Trust the proxy chain
        trusted_proxies = ["10.0.0.0/24"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should return the original client IP
        assert result == "203.0.113.1"

    def test_all_proxies_in_chain_trusted(self):
        """Test when all IPs in chain are trusted proxies."""
        headers = {"x-forwarded-for": "10.0.0.3, 10.0.0.1, 10.0.0.2"}
        request = self.create_mock_request("10.0.0.2", headers)
        
        trusted_proxies = ["10.0.0.0/24"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should fall back to direct IP when all forwarded IPs are trusted
        assert result == "10.0.0.2"

    def test_invalid_ip_in_headers(self):
        """Test handling of invalid IP addresses in headers."""
        headers = {
            "x-forwarded-for": "invalid-ip, 203.0.113.1",
            "x-real-ip": "also-invalid",
        }
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should skip invalid IPs and return valid one
        assert result == "203.0.113.1"

    def test_header_injection_protection(self):
        """Test protection against header injection attacks."""
        headers = {
            "x-forwarded-for": "203.0.113.1\r\nX-Injected: malicious",
            "x-real-ip": "203.0.113.2\nHost: evil.com",
        }
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should fall back to direct IP due to invalid header content
        assert result == "10.0.0.1"

    def test_empty_headers(self):
        """Test handling of empty or missing headers."""
        headers = {
            "x-forwarded-for": "",
            "x-real-ip": "",
            "forwarded": "",
        }
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should return direct IP when headers are empty
        assert result == "10.0.0.1"

    def test_no_client_object(self):
        """Test handling when request has no client object."""
        request = Mock()
        request.client = None
        request.headers = Mock()
        request.headers.get = lambda key, default="": ""
        
        result = get_client_ip(request)
        assert result == ""

    def test_priority_order(self):
        """Test that headers are checked in correct priority order."""
        headers = {
            "x-forwarded-for": "203.0.113.1",
            "x-real-ip": "203.0.113.2",
            "forwarded": "for=203.0.113.3",
        }
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # X-Forwarded-For should take priority
        assert result == "203.0.113.1"


class TestGenerateDeviceFingerprintWithProxy:
    """Test device fingerprinting with proxy IP support."""

    def create_mock_request(self, client_host="127.0.0.1", headers=None):
        """Create a mock request for fingerprinting tests."""
        request = Mock()
        request.client = Mock()
        request.client.host = client_host
        request.headers = Mock()
        
        default_headers = {
            "user-agent": "Mozilla/5.0 Test Browser",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate",
            "accept": "text/html,application/xhtml+xml",
        }
        if headers:
            default_headers.update(headers)
        
        def get_header(key, default=""):
            return default_headers.get(key.lower(), default)
        
        request.headers.get = get_header
        return request

    def test_fingerprint_with_direct_ip(self):
        """Test fingerprint generation with direct IP."""
        request = self.create_mock_request("192.168.1.100")
        
        fingerprint = generate_device_fingerprint(request)
        
        # Should be a valid SHA256 hex string
        assert len(fingerprint) == 64
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_fingerprint_with_proxy_ip(self):
        """Test fingerprint generation with proxy IP extraction."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        fingerprint = generate_device_fingerprint(request, trusted_proxies)
        
        # Should be different from direct IP fingerprint
        direct_fingerprint = generate_device_fingerprint(
            self.create_mock_request("10.0.0.1")
        )
        assert fingerprint != direct_fingerprint

    def test_fingerprint_consistency(self):
        """Test that fingerprints are consistent for same input."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request1 = self.create_mock_request("10.0.0.1", headers)
        request2 = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        fingerprint1 = generate_device_fingerprint(request1, trusted_proxies)
        fingerprint2 = generate_device_fingerprint(request2, trusted_proxies)
        
        assert fingerprint1 == fingerprint2

    def test_fingerprint_changes_with_ip(self):
        """Test that fingerprint changes when IP changes."""
        base_headers = {"x-forwarded-for": "203.0.113.1"}
        different_headers = {"x-forwarded-for": "203.0.113.2"}
        
        request1 = self.create_mock_request("10.0.0.1", base_headers)
        request2 = self.create_mock_request("10.0.0.1", different_headers)
        
        trusted_proxies = ["10.0.0.1"]
        fingerprint1 = generate_device_fingerprint(request1, trusted_proxies)
        fingerprint2 = generate_device_fingerprint(request2, trusted_proxies)
        
        assert fingerprint1 != fingerprint2


class TestIPValidationSecurity:
    """Test security aspects of IP validation."""

    def create_mock_request(self, client_host="127.0.0.1", headers=None):
        """Create a mock request for security tests."""
        request = Mock()
        request.client = Mock()
        request.client.host = client_host
        request.headers = Mock()
        
        headers = headers or {}
        def get_header(key, default=""):
            return headers.get(key.lower(), default)
        
        request.headers.get = get_header
        return request

    def test_ip_spoofing_prevention(self):
        """Test that IP spoofing via headers is prevented."""
        # Attacker tries to spoof IP via headers from untrusted source
        headers = {"x-forwarded-for": "127.0.0.1"}  # Try to look like localhost
        request = self.create_mock_request("203.0.113.1", headers)
        
        # No trusted proxies - should ignore headers
        result = get_client_ip(request)
        assert result == "203.0.113.1"  # Real connecting IP
        
        # Trust different proxy - should still ignore
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "203.0.113.1"

    def test_proxy_chain_spoofing(self):
        """Test protection against proxy chain spoofing."""
        # Attacker includes trusted proxy in X-Forwarded-For
        headers = {"x-forwarded-for": "malicious.ip, 10.0.0.1"}
        request = self.create_mock_request("203.0.113.1", headers)  # Untrusted source
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should ignore header since request doesn't come from trusted proxy
        assert result == "203.0.113.1"

    def test_invalid_cidr_handling(self):
        """Test handling of invalid CIDR notations."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("10.0.0.1", headers)
        
        # Invalid CIDR should be ignored
        trusted_proxies = ["invalid-cidr/24", "10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should still work with valid proxy in list
        assert result == "203.0.113.1"

    def test_private_ip_in_forwarded_headers(self):
        """Test handling of private IPs in forwarded headers."""
        headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        request = self.create_mock_request("10.0.0.2", headers)
        
        trusted_proxies = ["10.0.0.0/24"]
        result = get_client_ip(request, trusted_proxies)
        
        # Should return private IP if it's the real client
        assert result == "192.168.1.1"

    def test_ipv6_support(self):
        """Test IPv6 address support in proxy headers."""
        headers = {"x-forwarded-for": "2001:db8::1"}
        request = self.create_mock_request("::1", headers)
        
        trusted_proxies = ["::1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "2001:db8::1"

    def test_mixed_ipv4_ipv6_chain(self):
        """Test mixed IPv4/IPv6 in proxy chain."""
        headers = {"x-forwarded-for": "2001:db8::1, 10.0.0.1"}
        request = self.create_mock_request("10.0.0.1", headers)
        
        trusted_proxies = ["10.0.0.1"]
        result = get_client_ip(request, trusted_proxies)
        assert result == "2001:db8::1"


class TestTrustedProxyConfiguration:
    """Test trusted proxy configuration helpers."""

    def test_get_common_trusted_proxies(self):
        """Test that common proxy configurations are available."""
        presets = get_common_trusted_proxies()
        
        # Check that expected presets exist
        expected_presets = [
            "aws_alb", "cloudflare", "google_cloud", "azure",
            "nginx_local", "docker_bridge", "kubernetes", "rfc1918"
        ]
        
        for preset in expected_presets:
            assert preset in presets
            assert isinstance(presets[preset], list)
            assert len(presets[preset]) > 0

    def test_configure_trusted_proxies_with_preset(self):
        """Test configuring trusted proxies with preset."""
        proxies = configure_trusted_proxies("nginx_local")
        
        assert "127.0.0.1" in proxies
        assert "::1" in proxies

    def test_configure_trusted_proxies_with_custom_list(self):
        """Test configuring trusted proxies with custom list."""
        custom_proxies = ["10.0.0.1", "192.168.1.0/24"]
        proxies = configure_trusted_proxies(custom_proxies)
        
        assert proxies == custom_proxies

    def test_configure_trusted_proxies_with_preset_and_additional(self):
        """Test combining preset with additional proxies."""
        additional = ["203.0.113.1"]
        proxies = configure_trusted_proxies("nginx_local", additional)
        
        assert "127.0.0.1" in proxies
        assert "::1" in proxies
        assert "203.0.113.1" in proxies

    def test_configure_trusted_proxies_unknown_preset(self):
        """Test error handling for unknown preset."""
        with pytest.raises(ValueError, match="Unknown proxy preset"):
            configure_trusted_proxies("unknown_preset")

    def test_configure_trusted_proxies_invalid_type(self):
        """Test error handling for invalid proxy_config type."""
        with pytest.raises(ValueError, match="proxy_config must be a string"):
            configure_trusted_proxies(123)

    def test_configure_trusted_proxies_none(self):
        """Test configuring with no proxy config."""
        proxies = configure_trusted_proxies(None)
        assert proxies == []

    def test_configure_trusted_proxies_only_additional(self):
        """Test configuring with only additional proxies."""
        additional = ["10.0.0.1", "10.0.0.2"]
        proxies = configure_trusted_proxies(None, additional)
        assert proxies == additional

    def test_cloudflare_preset_has_expected_ranges(self):
        """Test that Cloudflare preset includes expected IP ranges."""
        presets = get_common_trusted_proxies()
        cloudflare_ranges = presets["cloudflare"]
        
        # Check for some known Cloudflare ranges
        assert "173.245.48.0/20" in cloudflare_ranges
        assert "103.21.244.0/22" in cloudflare_ranges

    def test_rfc1918_preset_has_private_ranges(self):
        """Test that RFC1918 preset includes all private ranges."""
        presets = get_common_trusted_proxies()
        rfc1918_ranges = presets["rfc1918"]
        
        assert "10.0.0.0/8" in rfc1918_ranges
        assert "172.16.0.0/12" in rfc1918_ranges
        assert "192.168.0.0/16" in rfc1918_ranges


class TestProxyConfigurationIntegration:
    """Test integration of proxy configuration with IP extraction."""

    def create_mock_request(self, client_host="127.0.0.1", headers=None):
        """Create a mock request for integration tests."""
        request = Mock()
        request.client = Mock()
        request.client.host = client_host
        request.headers = Mock()
        
        headers = headers or {}
        def get_header(key, default=""):
            return headers.get(key.lower(), default)
        
        request.headers.get = get_header
        return request

    def test_nginx_local_preset_integration(self):
        """Test using nginx_local preset for IP extraction."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("127.0.0.1", headers)
        
        # Use preset configuration
        trusted_proxies = configure_trusted_proxies("nginx_local")
        result = get_client_ip(request, trusted_proxies)
        
        assert result == "203.0.113.1"

    def test_docker_bridge_preset_integration(self):
        """Test using docker_bridge preset for IP extraction."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("172.17.0.1", headers)
        
        trusted_proxies = configure_trusted_proxies("docker_bridge")
        result = get_client_ip(request, trusted_proxies)
        
        assert result == "203.0.113.1"

    def test_combined_preset_and_custom_integration(self):
        """Test combining preset with custom proxy for IP extraction."""
        headers = {"x-forwarded-for": "203.0.113.1"}
        request = self.create_mock_request("10.1.0.1", headers)
        
        # Combine nginx preset with custom proxy
        trusted_proxies = configure_trusted_proxies("nginx_local", ["10.1.0.1"])
        result = get_client_ip(request, trusted_proxies)
        
        assert result == "203.0.113.1"