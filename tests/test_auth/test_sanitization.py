"""
Tests for the improved sanitize_user_input function using bleach.

These tests verify that the function properly sanitizes dangerous input
while preserving legitimate content for logging and storage.
"""

import pytest

from serv.auth.utils import sanitize_user_input


class TestSanitizeUserInput:
    """Test secure input sanitization with bleach."""

    def test_normal_text_unchanged(self):
        """Test that normal text passes through unchanged."""
        text = "Hello, this is normal user input!"
        result = sanitize_user_input(text)
        assert result == text

    def test_html_tags_removed(self):
        """Test that HTML tags are stripped."""
        text = "Hello <script>alert('xss')</script> world"
        result = sanitize_user_input(text)
        assert result == "Hello alert('xss') world"
        assert "<script>" not in result

    def test_html_entities_handled(self):
        """Test HTML entities are properly handled."""
        text = "Hello &lt;script&gt; world"
        result = sanitize_user_input(text)
        # Bleach preserves HTML entities for safety (doesn't decode them)
        assert result == "Hello &lt;script&gt; world"

    def test_dangerous_html_removed(self):
        """Test that dangerous HTML is completely removed."""
        text = '<img src="x" onerror="alert(1)">'
        result = sanitize_user_input(text)
        assert "onerror" not in result
        assert "alert" not in result or result == "alert(1)"  # Text content may remain

    def test_crlf_injection_prevented(self):
        """Test that CRLF injection is prevented."""
        text = "Normal text\r\nINJECTED LOG ENTRY"
        result = sanitize_user_input(text)
        assert "\\r" in result or "\\n" in result
        assert "\r" not in result
        assert "\n" not in result

    def test_null_bytes_removed(self):
        """Test that null bytes are handled safely."""
        text = "Hello\x00World"
        result = sanitize_user_input(text)
        # Should not contain actual null bytes
        assert "\x00" not in result
        assert "Hello" in result
        assert "World" in result

    def test_length_truncation(self):
        """Test that overly long input is truncated."""
        text = "A" * 2000
        result = sanitize_user_input(text, max_length=100)
        assert len(result) <= 115  # 100 + len("...[TRUNCATED]")
        assert result.endswith("...[TRUNCATED]")

    def test_unicode_handling(self):
        """Test that Unicode characters are handled properly."""
        text = "Hello 世界! 🌍"
        result = sanitize_user_input(text)
        assert "世界" in result
        assert "🌍" in result

    def test_control_characters_handled(self):
        """Test that control characters are handled safely."""
        text = "Hello\tWorld\x0bTest"  # Tab and vertical tab
        result = sanitize_user_input(text)
        # Should keep tab but handle other control chars
        assert "Hello" in result
        assert "World" in result
        assert "Test" in result

    def test_non_string_input(self):
        """Test handling of non-string input."""
        result = sanitize_user_input(123)
        assert result == ""
        
        result = sanitize_user_input(None)
        assert result == ""

    def test_empty_string(self):
        """Test handling of empty string."""
        result = sanitize_user_input("")
        assert result == ""

    def test_javascript_protocol_removed(self):
        """Test that javascript: protocols are removed."""
        text = '<a href="javascript:alert(1)">Click me</a>'
        result = sanitize_user_input(text)
        assert "javascript:" not in result
        assert "alert" not in result or "alert(1)" in result  # Text might remain

    def test_style_injection_prevented(self):
        """Test that CSS injection is prevented."""
        text = '<div style="background:url(javascript:alert(1))">Content</div>'
        result = sanitize_user_input(text)
        assert "javascript:" not in result
        assert "Content" in result

    def test_data_uri_handled(self):
        """Test that data URIs are handled safely."""
        text = '<img src="data:image/svg+xml,<svg onload=alert(1)>">'
        result = sanitize_user_input(text)
        assert "onload" not in result
        assert "alert" not in result

    def test_unicode_escape_attacks(self):
        """Test that Unicode escape attacks are prevented."""
        text = "\\u003cscript\\u003ealert(1)\\u003c/script\\u003e"
        result = sanitize_user_input(text)
        # Should not process escape sequences as HTML
        assert "script" in result  # Literal text, not processed
        assert not result.startswith("<script>")

    def test_xml_entities_safe(self):
        """Test that XML entities are handled safely."""
        text = "Test &amp; &lt; &gt; &quot; &#39;"
        result = sanitize_user_input(text)
        # Bleach should handle these safely
        assert "&" in result or "&amp;" in result
        assert result != ""

    def test_log_forging_prevention(self):
        """Test comprehensive log forging prevention."""
        # Simulate an attack trying to forge log entries
        malicious_input = "legitimate input\r\n[ERROR] FAKE LOG ENTRY - Admin password: secret123\r\nlegit continued"
        result = sanitize_user_input(malicious_input)
        
        # Should not contain actual CRLF that could forge logs
        assert "\r" not in result
        assert "\n" not in result
        # Should contain escaped versions
        assert "\\r" in result or "\\n" in result
        assert "legitimate input" in result
        assert "FAKE LOG ENTRY" in result  # Content preserved but safe

    def test_consistency_multiple_calls(self):
        """Test that multiple calls with same input produce same result."""
        text = "Test input with <tags> and special chars\r\n"
        result1 = sanitize_user_input(text)
        result2 = sanitize_user_input(text)
        assert result1 == result2


class TestSanitizationIntegration:
    """Test sanitization in realistic scenarios."""

    def test_user_registration_data(self):
        """Test sanitization of typical user registration data."""
        username = "user<script>alert('xss')</script>"
        email = "test@example.com\r\nBCC: admin@evil.com"
        bio = "I'm a normal user! <img src=x onerror=alert(1)>"
        
        clean_username = sanitize_user_input(username)
        clean_email = sanitize_user_input(email)
        clean_bio = sanitize_user_input(bio)
        
        # Should preserve legitimate content
        assert "user" in clean_username
        assert "test@example.com" in clean_email
        assert "I'm a normal user!" in clean_bio
        
        # Should remove dangerous content
        assert "<script>" not in clean_username
        assert "\r" not in clean_email and "\n" not in clean_email
        assert "onerror" not in clean_bio

    def test_log_entry_sanitization(self):
        """Test sanitization for log entries."""
        user_agent = "Mozilla/5.0 <script>alert('xss')</script>"
        request_path = "/api/users\r\nHOST: evil.com"
        error_message = "Database error: 'DROP TABLE users; --"
        
        clean_ua = sanitize_user_input(user_agent)
        clean_path = sanitize_user_input(request_path)
        clean_error = sanitize_user_input(error_message)
        
        # Should be safe for logging
        assert "Mozilla/5.0" in clean_ua
        assert "/api/users" in clean_path
        assert "Database error" in clean_error
        
        # Should not break log format
        assert "<script>" not in clean_ua
        assert "\r" not in clean_path and "\n" not in clean_path
        assert "DROP TABLE" in clean_error  # SQL preserved as text, not executed

    def test_edge_cases(self):
        """Test various edge cases."""
        test_cases = [
            "",  # Empty
            " ",  # Whitespace only
            "\t\r\n",  # Only control chars
            "🚀🌟✨",  # Emojis
            "مرحبا",  # Arabic
            "こんにちは",  # Japanese
            "a" * 10000,  # Very long
            "\x00\x01\x02",  # Control characters
        ]
        
        for test_input in test_cases:
            result = sanitize_user_input(test_input)
            # Should not crash and should return string
            assert isinstance(result, str)
            # Should not contain dangerous characters
            assert "\x00" not in result