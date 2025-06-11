"""
Tests for the auth configuration system and factory.

These tests verify that the auth configuration system can properly load
concrete implementations and register them in the DI container.
"""

import pytest
from unittest.mock import Mock

from bevy import Container, get_registry

from serv.auth import (
    AuthConfigError, 
    AuthSystemFactory, 
    BackendLoader,
    create_auth_system,
    AuthProvider,
    SessionManager,
    CredentialVault,
    RateLimiter,
    TokenService
)


class TestBackendLoader:
    """Test the backend loading functionality."""
    
    def test_load_class_success(self):
        """Test loading a valid class."""
        loader = BackendLoader()
        cls = loader.load_class("builtins:dict")
        assert cls is dict
    
    def test_load_class_invalid_format(self):
        """Test loading with invalid module path format."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Invalid module path format"):
            loader.load_class("invalid_format")
    
    def test_load_class_missing_module(self):
        """Test loading from non-existent module."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Could not import module"):
            loader.load_class("nonexistent.module:Class")
    
    def test_load_class_missing_class(self):
        """Test loading non-existent class from valid module."""
        loader = BackendLoader()
        with pytest.raises(AuthConfigError, match="Class.*not found"):
            loader.load_class("builtins:NonExistentClass")


class MockAuthProvider(AuthProvider):
    """Mock auth provider for testing."""
    
    def _validate_config(self, config):
        pass
    
    async def authenticate(self, credentials, request_context=None):
        return Mock()
    
    async def refresh_authentication(self, refresh_token, request_context=None):
        return Mock()
    
    async def validate_session(self, session_token, request_context=None):
        return Mock()
    
    async def initiate_auth(self, request_context=None):
        return Mock()
    
    async def refresh_session(self, refresh_token, request_context=None):
        return Mock()
    
    async def validate_credential(self, credential_data, request_context=None):
        return Mock()
    
    async def cleanup(self):
        pass


class MockSessionManager(SessionManager):
    """Mock session manager for testing."""
    
    def _validate_config(self, config):
        pass
    
    async def create_session(self, user_data, request_context=None):
        return Mock()
    
    async def get_session(self, session_id, request_context=None):
        return Mock()
    
    async def update_session(self, session_id, data, request_context=None):
        return Mock()
    
    async def delete_session(self, session_id, request_context=None):
        return Mock()
    
    async def cleanup_expired_sessions(self):
        pass
    
    async def cleanup(self):
        pass
    
    async def extend_session(self, session_id, extension_time, request_context=None):
        return Mock()
    
    async def invalidate_session(self, session_id, request_context=None):
        return Mock()
    
    async def invalidate_user_sessions(self, user_id, exclude_session=None, request_context=None):
        return Mock()
    
    async def validate_session(self, session_token, request_context=None):
        return Mock()


class MockCredentialVault(CredentialVault):
    """Mock credential vault for testing."""
    
    def _validate_config(self, config):
        pass
    
    async def store_credentials(self, user_id, credentials, metadata=None):
        return Mock()
    
    async def verify_credentials(self, user_id, credentials):
        return Mock()
    
    async def update_credentials(self, user_id, new_credentials, metadata=None):
        return Mock()
    
    async def delete_credentials(self, user_id):
        return Mock()
    
    async def cleanup(self):
        pass
    
    async def hash_credential(self, credential_data, metadata=None):
        return Mock()
    
    async def list_user_credentials(self, user_id, credential_type=None):
        return Mock()
    
    async def rotate_credential(self, user_id, credential_type, new_credential, metadata=None):
        return Mock()


class MockRateLimiter(RateLimiter):
    """Mock rate limiter for testing."""
    
    def _validate_config(self, config):
        pass
    
    async def check_rate_limit(self, identifier, action, limit_override=None):
        return Mock()
    
    async def record_action(self, identifier, action, count=1):
        pass
    
    async def reset_limit(self, identifier, action=None):
        pass
    
    async def get_limit_status(self, identifier, action):
        return Mock()
    
    async def cleanup(self):
        pass
    
    async def configure_limit(self, action, limit, window):
        pass
    
    async def get_configured_limits(self):
        return Mock()


class MockTokenService(TokenService):
    """Mock token service for testing."""
    
    def _validate_config(self, config):
        pass
    
    async def generate_token(self, user_data, token_type="access", expiry=None):
        return Mock()
    
    async def validate_token(self, token, expected_type="access"):
        return Mock()
    
    async def refresh_token(self, refresh_token):
        return Mock()
    
    async def revoke_token(self, token):
        pass
    
    async def cleanup(self):
        pass
    
    async def get_token_metadata(self, token):
        return Mock()
    
    async def revoke_user_tokens(self, user_id, token_type=None):
        pass


class TestAuthSystemFactory:
    """Test the auth system factory."""
    
    def setup_method(self):
        """Set up test container."""
        registry = get_registry()
        self.container = registry.create_container()
        self.factory = AuthSystemFactory(self.container)
    
    def test_create_auth_provider_jwt(self):
        """Test creating JWT auth provider."""
        config = {
            'type': 'jwt',
            'config': {
                'secret_key': 'test-secret',
                'algorithm': 'HS256'
            }
        }
        
        # Mock the loader to return our mock class for the JWT provider path
        def mock_load_class(path):
            if path == 'serv.bundled.auth.providers.jwt_provider:JwtAuthProvider':
                return MockAuthProvider
            raise ValueError(f"Unexpected path: {path}")
        
        self.factory._loader.load_class = mock_load_class
        
        provider = self.factory.create_auth_provider(config)
        assert isinstance(provider, MockAuthProvider)
        assert provider.config == config['config']
    
    def test_create_auth_provider_missing_type(self):
        """Test creating auth provider without type."""
        config = {'config': {'secret': 'test'}}
        
        with pytest.raises(AuthConfigError, match="missing 'type' field"):
            self.factory.create_auth_provider(config)
    
    def test_create_auth_provider_unknown_type(self):
        """Test creating auth provider with unknown type."""
        config = {'type': 'unknown', 'config': {}}
        
        with pytest.raises(AuthConfigError, match="Unknown auth provider type"):
            self.factory.create_auth_provider(config)
    
    def test_create_session_storage(self):
        """Test creating session storage."""
        config = {
            'backend': 'test.module:MockSessionManager',
            'database_qualifier': 'auth',
            'session_timeout': 3600
        }
        
        # Mock the loader
        self.factory._loader.load_class = lambda path: MockSessionManager
        
        storage = self.factory.create_session_storage(config)
        assert isinstance(storage, MockSessionManager)
        assert storage.config['database_qualifier'] == 'auth'
        assert 'backend' not in storage.config  # Should be excluded
    
    def test_create_session_storage_missing_backend(self):
        """Test creating session storage without backend."""
        config = {'database_qualifier': 'auth'}
        
        with pytest.raises(AuthConfigError, match="missing 'backend' field"):
            self.factory.create_session_storage(config)
    
    def test_create_credential_vault(self):
        """Test creating credential vault."""
        config = {
            'backend': 'test.module:MockCredentialVault',
            'bcrypt_rounds': 12
        }
        
        # Mock the loader
        self.factory._loader.load_class = lambda path: MockCredentialVault
        
        vault = self.factory.create_credential_vault(config)
        assert isinstance(vault, MockCredentialVault)
        assert vault.config['bcrypt_rounds'] == 12
    
    def test_create_rate_limiter(self):
        """Test creating rate limiter."""
        config = {
            'backend': 'test.module:MockRateLimiter',
            'default_limits': {'login': '5/min'}
        }
        
        # Mock the loader
        self.factory._loader.load_class = lambda path: MockRateLimiter
        
        limiter = self.factory.create_rate_limiter(config)
        assert isinstance(limiter, MockRateLimiter)
        assert limiter.config['default_limits'] == {'login': '5/min'}
    
    def test_configure_auth_system_full(self):
        """Test configuring a complete auth system."""
        auth_config = {
            'providers': [
                {'type': 'jwt', 'config': {'secret_key': 'test'}}
            ],
            'storage': {
                'backend': 'test.module:MockSessionManager',
                'database_qualifier': 'auth'
            },
            'credential_vault': {
                'backend': 'test.module:MockCredentialVault',
                'bcrypt_rounds': 12
            },
            'rate_limiting': {
                'backend': 'test.module:MockRateLimiter',
                'default_limits': {'login': '5/min'}
            },
            'token_service': {
                'backend': 'test.module:MockTokenService',
                'expiry_time': 3600
            }
        }
        
        # Mock all loaders
        def mock_loader(path):
            if 'jwt_provider:JwtAuthProvider' in path:
                return MockAuthProvider
            elif 'MockSessionManager' in path:
                return MockSessionManager
            elif 'MockCredentialVault' in path:
                return MockCredentialVault
            elif 'MockRateLimiter' in path:
                return MockRateLimiter
            elif 'MockTokenService' in path:
                return MockTokenService
            else:
                raise ValueError(f"Unknown path: {path}")
        
        self.factory._loader.load_class = mock_loader
        
        components = self.factory.configure_auth_system(auth_config)
        
        # Verify all components were created
        assert 'providers' in components
        assert 'storage' in components
        assert 'credential_vault' in components
        assert 'rate_limiter' in components
        assert 'token_service' in components
        
        # Verify types are registered in DI container using abstract base classes
        assert self.container.get(AuthProvider) is not None
        assert self.container.get(SessionManager) is not None
        assert self.container.get(CredentialVault) is not None
        assert self.container.get(RateLimiter) is not None
        assert self.container.get(TokenService) is not None
    
    def test_configure_auth_system_partial(self):
        """Test configuring auth system with only some components."""
        auth_config = {
            'providers': [
                {'type': 'jwt', 'config': {'secret_key': 'test'}}
            ],
            'storage': {
                'backend': 'test.module:MockSessionManager',
                'database_qualifier': 'auth'
            }
        }
        
        # Mock loaders
        def mock_loader(path):
            if 'jwt_provider:JwtAuthProvider' in path:
                return MockAuthProvider
            elif 'MockSessionManager' in path:
                return MockSessionManager
            else:
                raise ValueError(f"Unknown path: {path}")
        
        self.factory._loader.load_class = mock_loader
        
        components = self.factory.configure_auth_system(auth_config)
        
        # Verify only configured components exist
        assert 'providers' in components
        assert 'storage' in components
        assert 'credential_vault' not in components
        assert 'rate_limiter' not in components
        assert 'token_service' not in components
        
        # Verify only configured types are in DI container
        assert self.container.get(AuthProvider) is not None
        assert self.container.get(SessionManager) is not None
        
        # These should not be available
        with pytest.raises(Exception):
            self.container.get(CredentialVault)
        with pytest.raises(Exception):
            self.container.get(RateLimiter)
        with pytest.raises(Exception):
            self.container.get(TokenService)
    
    def test_configure_auth_system_empty(self):
        """Test configuring auth system with empty config."""
        components = self.factory.configure_auth_system({})
        
        assert components == {}
        
        # No types should be registered
        with pytest.raises(Exception):
            self.container.get(AuthProvider)


class TestCreateAuthSystem:
    """Test the convenience create_auth_system function."""
    
    def test_create_auth_system_with_new_container(self):
        """Test creating auth system with new container."""
        auth_config = {
            'providers': [
                {'type': 'jwt', 'config': {'secret_key': 'test'}}
            ]
        }
        
        # This would normally fail without mocking, but we test the interface
        with pytest.raises(AuthConfigError):
            create_auth_system(auth_config)
    
    def test_create_auth_system_with_existing_container(self):
        """Test creating auth system with existing container."""
        registry = get_registry()
        container = registry.create_container()
        
        auth_config = {
            'providers': [
                {'type': 'jwt', 'config': {'secret_key': 'test'}}
            ]
        }
        
        # This would normally fail without mocking, but we test the interface
        with pytest.raises(AuthConfigError):
            create_auth_system(auth_config, container)