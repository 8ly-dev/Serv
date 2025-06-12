"""
Example demonstrating X-Forwarded-For handling in Serv auth utilities.

This example shows how to properly configure and use the X-Forwarded-For
support for extracting real client IPs in production environments.
"""

from serv.auth.utils import (
    get_client_ip,
    generate_device_fingerprint, 
    configure_trusted_proxies,
    get_common_trusted_proxies
)


def example_basic_usage():
    """Basic example of extracting client IP with proxy support."""
    print("=== Basic X-Forwarded-For Usage ===")
    
    # Create a mock request (in real code, this comes from your web framework)
    class MockRequest:
        def __init__(self, client_host, headers):
            self.client = type('Client', (), {'host': client_host})()
            self.headers = headers
            
        def get_header(self, name, default=""):
            return self.headers.get(name.lower(), default)
    
    # Simulate request from Nginx reverse proxy
    request = MockRequest("127.0.0.1", {
        "x-forwarded-for": "203.0.113.1, 10.0.0.5",
        "x-real-ip": "203.0.113.1"
    })
    
    # Configure trusted proxies (Nginx running on localhost)
    trusted_proxies = ["127.0.0.1", "::1"]
    
    # Extract real client IP
    client_ip = get_client_ip(request, trusted_proxies)
    print(f"Real client IP: {client_ip}")
    # Output: Real client IP: 203.0.113.1


def example_common_presets():
    """Example using common proxy configuration presets."""
    print("\n=== Using Common Proxy Presets ===")
    
    # View available presets
    presets = get_common_trusted_proxies()
    print("Available presets:", list(presets.keys()))
    
    # Configure for Nginx deployment
    nginx_proxies = configure_trusted_proxies("nginx_local")
    print(f"Nginx local proxies: {nginx_proxies}")
    
    # Configure for Docker deployment
    docker_proxies = configure_trusted_proxies("docker_bridge")
    print(f"Docker bridge proxies: {docker_proxies}")
    
    # Configure for Cloudflare deployment
    cloudflare_proxies = configure_trusted_proxies("cloudflare")
    print(f"Cloudflare proxies: {len(cloudflare_proxies)} ranges configured")


def example_custom_configuration():
    """Example of custom proxy configuration."""
    print("\n=== Custom Proxy Configuration ===")
    
    # Custom load balancer IPs
    custom_proxies = ["10.0.1.100", "10.0.1.101", "192.168.1.0/24"]
    
    # Combine preset with custom proxies
    all_proxies = configure_trusted_proxies("nginx_local", custom_proxies)
    print(f"Combined proxies: {all_proxies}")
    
    # Use only custom proxies
    only_custom = configure_trusted_proxies(custom_proxies)
    print(f"Custom only: {only_custom}")


def example_security_scenarios():
    """Example showing security considerations."""
    print("\n=== Security Scenarios ===")
    
    class MockRequest:
        def __init__(self, client_host, headers):
            self.client = type('Client', (), {'host': client_host})()
            self.headers = headers
            
        def get_header(self, name, default=""):
            return self.headers.get(name.lower(), default)
    
    # Scenario 1: Attacker tries to spoof IP from untrusted source
    malicious_request = MockRequest("203.0.113.99", {
        "x-forwarded-for": "127.0.0.1"  # Attacker trying to look like localhost
    })
    
    trusted_proxies = ["127.0.0.1"]  # Only trust localhost
    spoofed_ip = get_client_ip(malicious_request, trusted_proxies)
    print(f"Spoofing attempt result: {spoofed_ip}")
    # Output: 203.0.113.99 (ignores spoofed header)
    
    # Scenario 2: Legitimate request from trusted proxy
    legitimate_request = MockRequest("127.0.0.1", {
        "x-forwarded-for": "203.0.113.1"
    })
    
    real_ip = get_client_ip(legitimate_request, trusted_proxies)
    print(f"Legitimate request result: {real_ip}")
    # Output: 203.0.113.1 (trusts header from localhost)


def example_device_fingerprinting():
    """Example of device fingerprinting with proxy support."""
    print("\n=== Device Fingerprinting with Proxies ===")
    
    class MockRequest:
        def __init__(self, client_host, headers):
            self.client = type('Client', (), {'host': client_host})()
            self.headers = headers
            
        def get(self, name, default=""):
            return self.headers.get(name.lower(), default)
    
    # Mock request with typical browser headers
    request = MockRequest("10.0.0.1", {
        "x-forwarded-for": "203.0.113.1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })
    
    # Generate fingerprint with proxy support
    trusted_proxies = ["10.0.0.1"]
    fingerprint = generate_device_fingerprint(request, trusted_proxies)
    print(f"Device fingerprint: {fingerprint[:16]}...")
    
    # Generate fingerprint without proxy support (different result)
    direct_fingerprint = generate_device_fingerprint(request)
    print(f"Direct fingerprint: {direct_fingerprint[:16]}...")
    print(f"Fingerprints differ: {fingerprint != direct_fingerprint}")


def example_production_deployment():
    """Example production deployment configuration."""
    print("\n=== Production Deployment Example ===")
    
    # Common production setup: App behind nginx behind AWS ALB
    production_config = {
        # AWS Application Load Balancer + Nginx reverse proxy
        "trusted_proxies": configure_trusted_proxies(
            "aws_alb",  # Trust AWS private IP ranges
            ["10.0.1.50", "10.0.1.51"]  # Specific nginx instances
        )
    }
    
    print(f"Production trusted proxies: {len(production_config['trusted_proxies'])} configured")
    
    # Kubernetes deployment with ingress controller
    k8s_config = {
        "trusted_proxies": configure_trusted_proxies("kubernetes")
    }
    
    print(f"Kubernetes trusted proxies: {k8s_config['trusted_proxies']}")
    
    # Cloudflare CDN deployment
    cdn_config = {
        "trusted_proxies": configure_trusted_proxies("cloudflare")
    }
    
    print(f"Cloudflare CDN: {len(cdn_config['trusted_proxies'])} IP ranges")


if __name__ == "__main__":
    example_basic_usage()
    example_common_presets()
    example_custom_configuration()
    example_security_scenarios()
    example_device_fingerprinting()
    example_production_deployment()
    
    print("\n=== Summary ===")
    print("✅ X-Forwarded-For support prevents IP spoofing")
    print("✅ Common proxy presets for easy configuration")
    print("✅ CIDR notation support for network ranges")
    print("✅ Multiple proxy header support (X-Forwarded-For, X-Real-IP, Forwarded)")
    print("✅ IPv4 and IPv6 support")
    print("✅ Secure fallback to direct connection IP")