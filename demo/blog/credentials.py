"""Demo credential provider.

This very simple provider allows all requests and implements a minimal CSRF
token scheme suitable for demos only. Do not use in production.
"""

class DemoCredentialProvider:
    def has_credentials(self, permissions: set[str]) -> bool:
        # Allow everything for the demo.
        return True

    def generate_csrf_token(self) -> str:
        # Fixed token for demo simplicity. Do not use in production.
        return "demo-token"

    def validate_csrf_token(self, token: str) -> bool:
        return token == "demo-token"

