"""
Bundled authentication implementations for the Serv framework.

This package provides production-ready implementations of the authentication
interfaces using battle-tested security libraries.

Security-focused implementations:
- JWT authentication with algorithm confusion protection
- Memory-based rate limiting with sliding window algorithms
- Ommi-integrated session storage with lifecycle management
- bcrypt-based credential storage with secure defaults

All implementations follow the interface-based design allowing easy swapping
and configuration via serv.config.yaml.
"""
