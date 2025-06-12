# Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for the authentication system, ensuring security, reliability, and compliance through multiple testing approaches.

## Testing Pyramid

```
                    ┌─────────────────┐
                    │   E2E Tests     │  Security, Integration, User Flows
                    │    (10-15%)     │
                ┌───┴─────────────────┴───┐
                │   Integration Tests     │  Provider Interactions, Middleware
                │      (20-25%)           │
            ┌───┴─────────────────────────┴───┐
            │       Unit Tests                │  Individual Components, Logic
            │        (60-70%)                 │
            └─────────────────────────────────┘
```

## Unit Testing

### 1. Core Types and Data Structures

```python
# tests/auth/test_types.py
class TestUser:
    def test_user_creation(self):
        """Test User dataclass creation and validation."""
        user = User(
            id="123",
            username="testuser",
            email="test@example.com",
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow()
        )
        assert user.id == "123"
        assert user.is_active is True
    
    def test_user_serialization(self):
        """Test User to_dict() method."""
        user = User(id="123", username="test", ...)
        data = user.to_dict()
        
        assert data["id"] == "123"
        assert "created_at" in data
        assert isinstance(data["created_at"], str)
    
    def test_user_validation(self):
        """Test User validation rules."""
        with pytest.raises(ValidationError):
            User(id="", username="test", ...)  # Empty ID should fail

class TestSession:
    def test_session_expiry(self):
        """Test session expiration logic."""
        expired_session = Session(
            id="123",
            user_id="456",
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
            last_accessed=datetime.utcnow() - timedelta(hours=1)
        )
        assert expired_session.is_expired is True
    
    def test_time_remaining(self):
        """Test time remaining calculation."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        session = Session(expires_at=future_time, ...)
        
        assert session.time_remaining.total_seconds() > 3500  # ~1 hour

class TestPermission:
    def test_permission_string_representation(self):
        """Test Permission string format."""
        perm = Permission(resource="users", action="read")
        assert str(perm) == "read:users"
    
    def test_permission_equality(self):
        """Test Permission equality and hashing."""
        perm1 = Permission(resource="users", action="read")
        perm2 = Permission(resource="users", action="read")
        perm3 = Permission(resource="users", action="write")
        
        assert perm1 == perm2
        assert perm1 != perm3
        assert hash(perm1) == hash(perm2)
```

### 2. Audit System

```python
# tests/auth/audit/test_enforcement.py
class TestAuditEnforcement:
    def test_audit_required_decorator(self):
        """Test that @AuditRequired enforces event emission."""
        
        @AuditRequired(AuditEventType.AUTH_ATTEMPT)
        async def test_method(audit_emitter: AuditEmitter):
            # This should raise an exception because no event was emitted
            pass
        
        with pytest.raises(AuditViolationException) as exc_info:
            await test_method()
        
        assert "AUTH_ATTEMPT" in str(exc_info.value)
    
    def test_audit_event_emission(self):
        """Test successful audit event emission."""
        
        @AuditRequired(AuditEventType.AUTH_SUCCESS)
        async def test_method(audit_emitter: AuditEmitter):
            audit_emitter.emit(AuditEventType.AUTH_SUCCESS, user_id="123")
        
        # Should not raise an exception
        await test_method()
    
    def test_multiple_required_events(self):
        """Test multiple required events."""
        
        @AuditRequired(AuditEventType.AUTH_ATTEMPT, AuditEventType.AUTH_SUCCESS)
        async def test_method(audit_emitter: AuditEmitter):
            audit_emitter.emit(AuditEventType.AUTH_ATTEMPT, user_id="123")
            # Missing AUTH_SUCCESS event
        
        with pytest.raises(AuditViolationException):
            await test_method()

class TestAuditInheritance:
    def test_inheritance_enforcement(self):
        """Test that audit requirements cannot be overridden."""
        
        class BaseProvider(AuditEnforced):
            @AuditRequired(AuditEventType.AUTH_ATTEMPT)
            async def authenticate(self, audit_emitter: AuditEmitter):
                pass
        
        with pytest.raises(AuditInheritanceViolation):
            class ChildProvider(BaseProvider):
                @AuditRequired(AuditEventType.AUTH_SUCCESS)  # Different requirement
                async def authenticate(self, audit_emitter: AuditEmitter):
                    pass
    
    def test_valid_inheritance(self):
        """Test valid inheritance of audit requirements."""
        
        class BaseProvider(AuditEnforced):
            @AuditRequired(AuditEventType.AUTH_ATTEMPT)
            async def authenticate(self, audit_emitter: AuditEmitter):
                pass
        
        # This should work - same requirements
        class ChildProvider(BaseProvider):
            @AuditRequired(AuditEventType.AUTH_ATTEMPT)
            async def authenticate(self, audit_emitter: AuditEmitter):
                audit_emitter.emit(AuditEventType.AUTH_ATTEMPT)
```

### 3. Provider Implementations

```python
# tests/bundled/auth/test_memory_providers.py
class TestMemoryCredentialProvider:
    @pytest.fixture
    async def provider(self):
        return MemoryCredentialProvider()
    
    async def test_create_and_verify_credentials(self, provider):
        """Test credential creation and verification."""
        credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password123"
        )
        
        # Mock audit emitter
        mock_emitter = Mock()
        
        # Create credentials
        await provider.create_credentials("user123", credentials, mock_emitter)
        
        # Verify credentials
        result = await provider.verify_credentials(credentials, mock_emitter)
        assert result is True
        
        # Verify audit events were emitted
        assert mock_emitter.emit.call_count == 2  # CREATE and VERIFY
    
    async def test_invalid_credentials(self, provider):
        """Test verification of invalid credentials."""
        invalid_credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="nonexistent",
            secret="wrongpassword"
        )
        
        mock_emitter = Mock()
        result = await provider.verify_credentials(invalid_credentials, mock_emitter)
        assert result is False
    
    async def test_password_hashing(self, provider):
        """Test that passwords are properly hashed."""
        credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password123"
        )
        
        mock_emitter = Mock()
        await provider.create_credentials("user123", credentials, mock_emitter)
        
        # Check that raw password is not stored
        stored_hash = provider._credentials["user123"][CredentialType.PASSWORD]["secret"]
        assert stored_hash != "password123"
        assert len(stored_hash) > 50  # Hashed passwords are longer

class TestMemorySessionProvider:
    @pytest.fixture
    async def provider(self):
        return MemorySessionProvider()
    
    async def test_create_session(self, provider):
        """Test session creation."""
        mock_emitter = Mock()
        
        session = await provider.create_session(
            "user123",
            ip_address="192.168.1.1",
            user_agent="test-agent",
            audit_emitter=mock_emitter
        )
        
        assert session.user_id == "user123"
        assert session.ip_address == "192.168.1.1"
        assert not session.is_expired
        
        # Verify audit event
        mock_emitter.emit.assert_called_once_with(AuditEventType.SESSION_CREATE, session_id=session.id)
    
    async def test_session_expiration(self, provider):
        """Test session expiration handling."""
        mock_emitter = Mock()
        
        # Create session with very short duration
        session = await provider.create_session(
            "user123",
            duration=timedelta(milliseconds=1),
            audit_emitter=mock_emitter
        )
        
        # Wait for expiration
        await asyncio.sleep(0.002)
        
        # Try to retrieve expired session
        retrieved = await provider.get_session(session.id)
        assert retrieved is None  # Should be None for expired session
```

## Integration Testing

### 1. Provider Interactions

```python
# tests/auth/integration/test_provider_integration.py
class TestProviderIntegration:
    @pytest.fixture
    async def auth_system(self):
        """Set up complete auth system for testing."""
        credential_provider = MemoryCredentialProvider()
        session_provider = MemorySessionProvider()
        user_provider = MemoryUserProvider()
        audit_provider = MemoryAuditProvider()
        
        auth_provider = StandardAuthProvider(
            credential_provider,
            session_provider,
            user_provider,
            audit_provider
        )
        
        return auth_provider
    
    async def test_complete_auth_flow(self, auth_system):
        """Test complete authentication flow."""
        # Create user
        user = await auth_system.user_provider.create_user("testuser", "test@example.com")
        
        # Create credentials
        credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password123"
        )
        await auth_system.credential_provider.create_credentials(user.id, credentials)
        
        # Authenticate
        session = await auth_system.authenticate(
            credentials,
            ip_address="192.168.1.1",
            user_agent="test-agent"
        )
        
        assert session is not None
        assert session.user_id == user.id
        
        # Validate session
        validated_session = await auth_system.validate_session(session.id)
        assert validated_session.id == session.id
        
        # Get current user
        current_user = await auth_system.get_current_user(session.id)
        assert current_user.id == user.id
    
    async def test_authorization_flow(self, auth_system):
        """Test authorization checking."""
        # Set up user with permissions
        user = await auth_system.user_provider.create_user("testuser")
        await auth_system.user_provider.assign_role(user.id, "admin")
        
        # Create session
        credentials = Credentials(type=CredentialType.PASSWORD, identifier="testuser", secret="password")
        await auth_system.credential_provider.create_credentials(user.id, credentials)
        session = await auth_system.authenticate(credentials)
        
        # Test authorization
        permission = Permission(resource="users", action="read")
        authorized = await auth_system.authorize(session.id, permission)
        
        assert authorized is True  # Admin should have access
```

### 2. Database Integration

```python
# tests/auth/integration/test_database_integration.py
class TestDatabaseIntegration:
    @pytest.fixture
    async def db_container(self):
        """Set up test database container."""
        # Use testcontainers or similar for real database testing
        container = get_database_container()
        await container.start()
        
        yield container
        
        await container.stop()
    
    async def test_database_credential_provider(self, db_container):
        """Test database credential provider with real database."""
        provider = DatabaseCredentialProvider(db_container.connection)
        
        credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password123"
        )
        
        mock_emitter = Mock()
        
        # Test CRUD operations
        await provider.create_credentials("user123", credentials, mock_emitter)
        result = await provider.verify_credentials(credentials, mock_emitter)
        assert result is True
        
        # Update credentials
        new_credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="newpassword456"
        )
        await provider.update_credentials("user123", credentials, new_credentials, mock_emitter)
        
        # Verify old credentials don't work
        old_result = await provider.verify_credentials(credentials, mock_emitter)
        assert old_result is False
        
        # Verify new credentials work
        new_result = await provider.verify_credentials(new_credentials, mock_emitter)
        assert new_result is True
```

### 3. Configuration Integration

```python
# tests/auth/integration/test_configuration.py
class TestConfigurationIntegration:
    def test_config_loading(self, tmp_path):
        """Test configuration loading from YAML."""
        config_file = tmp_path / "test_config.yaml"
        config_content = """
        auth:
          enabled: true
          providers:
            credential:
              provider: "memory"
              config:
                password_min_length: 12
            session:
              provider: "memory"
              config:
                default_duration: "8h"
        """
        config_file.write_text(config_content)
        
        config = AuthConfigLoader.load_config(config_file)
        
        assert config.enabled is True
        assert config.providers.credential.type == ProviderType.MEMORY
        assert config.providers.session.type == ProviderType.MEMORY
    
    def test_environment_variable_substitution(self, tmp_path, monkeypatch):
        """Test environment variable substitution in config."""
        monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-123")
        
        config_file = tmp_path / "test_config.yaml"
        config_content = """
        auth:
          providers:
            session:
              config:
                secret_key: "${AUTH_SECRET_KEY}"
        """
        config_file.write_text(config_content)
        
        config = AuthConfigLoader.load_config(config_file)
        
        assert config.providers.session.config["secret_key"] == "test-secret-key-123"
```

## End-to-End Testing

### 1. Authentication Flows

```python
# tests/auth/e2e/test_auth_flows.py
class TestAuthenticationFlows:
    @pytest.fixture
    async def test_app(self):
        """Create test application with auth system."""
        app = create_test_app_with_auth()
        yield app
        await app.cleanup()
    
    async def test_login_logout_flow(self, test_app):
        """Test complete login/logout flow."""
        async with TestClient(test_app) as client:
            # Try accessing protected route without auth
            response = await client.get("/protected")
            assert response.status_code == 401
            
            # Login
            login_response = await client.post("/auth/login", json={
                "username": "testuser",
                "password": "password123"
            })
            assert login_response.status_code == 200
            
            # Access protected route after login
            response = await client.get("/protected")
            assert response.status_code == 200
            
            # Logout
            logout_response = await client.post("/auth/logout")
            assert logout_response.status_code == 200
            
            # Try accessing protected route after logout
            response = await client.get("/protected")
            assert response.status_code == 401
    
    async def test_session_expiration(self, test_app):
        """Test session expiration handling."""
        async with TestClient(test_app) as client:
            # Login with short session duration
            await client.post("/auth/login", json={
                "username": "testuser",
                "password": "password123",
                "remember_me": False
            })
            
            # Access should work initially
            response = await client.get("/protected")
            assert response.status_code == 200
            
            # Wait for session to expire (mock time advancement)
            with freeze_time() as frozen_time:
                frozen_time.tick(delta=timedelta(hours=9))  # Advance past session expiry
                
                response = await client.get("/protected")
                assert response.status_code == 401
```

### 2. Route Protection

```python
# tests/auth/e2e/test_route_protection.py
class TestRouteProtection:
    @pytest.fixture
    async def protected_app(self):
        """Create app with protected routes."""
        app = create_app_with_protected_routes()
        yield app
        await app.cleanup()
    
    async def test_role_based_protection(self, protected_app):
        """Test role-based route protection."""
        async with TestClient(protected_app) as client:
            # Login as regular user
            await client.post("/auth/login", json={
                "username": "user",
                "password": "password"
            })
            
            # Access user route - should work
            response = await client.get("/user/profile")
            assert response.status_code == 200
            
            # Access admin route - should fail
            response = await client.get("/admin/users")
            assert response.status_code == 403
            
            # Login as admin
            await client.post("/auth/logout")
            await client.post("/auth/login", json={
                "username": "admin",
                "password": "adminpass"
            })
            
            # Access admin route - should work
            response = await client.get("/admin/users")
            assert response.status_code == 200
    
    async def test_permission_based_protection(self, protected_app):
        """Test permission-based route protection."""
        async with TestClient(protected_app) as client:
            # Login as user with specific permissions
            await client.post("/auth/login", json={
                "username": "editor",
                "password": "password"
            })
            
            # Test different permission levels
            response = await client.get("/posts")  # read:posts
            assert response.status_code == 200
            
            response = await client.post("/posts", json={"title": "Test"})  # write:posts
            assert response.status_code == 200
            
            response = await client.delete("/posts/1")  # delete:posts - should fail
            assert response.status_code == 403
```

## Security Testing

Security testing is a critical component with dedicated offensive and defensive testing approaches to ensure the authentication system is robust against real-world attacks.

### 1. Offensive Security Testing (Red Team)

```python
# tests/auth/security/test_offensive.py
class TestInjectionAttacks:
    """Test resistance to various injection attacks."""
    
    async def test_sql_injection_resistance(self, auth_system):
        """Test resistance to SQL injection attacks."""
        sql_payloads = [
            "admin'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; UPDATE users SET is_admin=true WHERE username='attacker'; --",
            "admin' UNION SELECT password FROM users WHERE username='admin' --",
            "'; INSERT INTO users (username, password) VALUES ('hacker', 'password'); --"
        ]
        
        for payload in sql_payloads:
            credentials = Credentials(
                type=CredentialType.PASSWORD,
                identifier=payload,
                secret="password"
            )
            
            # Should not succeed or cause database errors
            result = await auth_system.authenticate(credentials)
            assert result is None
    
    async def test_nosql_injection_resistance(self, auth_system):
        """Test resistance to NoSQL injection attacks."""
        nosql_payloads = [
            {"$ne": None},
            {"$regex": ".*"},
            {"$where": "this.username == 'admin'"},
            {"$gt": ""},
            {"username": {"$regex": "admin"}}
        ]
        
        for payload in nosql_payloads:
            # Attempt to inject malicious queries
            with pytest.raises((TypeError, ValueError, AuthenticationError)):
                await auth_system.authenticate_with_dict(payload)
    
    async def test_ldap_injection_resistance(self, auth_system):
        """Test resistance to LDAP injection attacks (future)."""
        ldap_payloads = [
            "admin)(|(password=*))",
            "admin)(&(password=*))",
            "*)(uid=*",
            "admin)(mail=*)"
        ]
        
        # Should be safe even if LDAP provider added later
        for payload in ldap_payloads:
            result = await auth_system.authenticate(Credentials(
                type=CredentialType.PASSWORD,
                identifier=payload,
                secret="password"
            ))
            assert result is None

class TestTimingAttacks:
    """Test resistance to timing-based attacks."""
    
    async def test_password_verification_timing(self, auth_system):
        """Test constant-time password verification."""
        valid_user = "testuser"
        invalid_user = "nonexistentuser" * 10  # Long username
        short_password = "abc"
        long_password = "a" * 1000
        
        # Create test user
        await auth_system.user_provider.create_user(
            User(username=valid_user, email="test@example.com")
        )
        await auth_system.credential_provider.store_credentials(
            valid_user, Credentials(
                type=CredentialType.PASSWORD,
                identifier=valid_user,
                secret="correct_password"
            )
        )
        
        # Test timing consistency  
        test_cases = [
            (valid_user, "wrong_password"),
            (invalid_user, "any_password"),
            (valid_user, short_password),
            (valid_user, long_password)
        ]
        
        times = []
        for username, password in test_cases:
            start_time = time.perf_counter()
            
            credentials = Credentials(
                type=CredentialType.PASSWORD,
                identifier=username,
                secret=password
            )
            
            result = await auth_system.authenticate(credentials)
            end_time = time.perf_counter()
            
            times.append(end_time - start_time)
        
        # All authentication attempts should take similar time
        max_time = max(times)
        min_time = min(times)
        time_variance = (max_time - min_time) / min_time
        
        # Should be within 20% variance (accounts for system noise)
        assert time_variance < 0.2, f"Timing variance too high: {time_variance}"
    
    async def test_user_enumeration_protection(self, auth_system):
        """Test protection against user enumeration via timing."""
        existing_user = "realuser"
        fake_users = ["fakeuser1", "fakeuser2", "fakeuser3"]
        
        # Create one real user
        await auth_system.user_provider.create_user(
            User(username=existing_user, email="real@example.com")
        )
        
        # Test authentication timing for existing vs non-existing users
        all_users = [existing_user] + fake_users
        times = []
        
        for username in all_users:
            start_time = time.perf_counter()
            
            result = await auth_system.authenticate(Credentials(
                type=CredentialType.PASSWORD,
                identifier=username,
                secret="wrong_password"
            ))
            
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        # All failed authentications should take similar time
        time_variance = (max(times) - min(times)) / min(times)
        assert time_variance < 0.2, "User enumeration possible via timing"

class TestSessionAttacks:
    """Test resistance to session-based attacks."""
    
    async def test_session_fixation_protection(self, auth_system):
        """Test protection against session fixation attacks."""
        # Create initial anonymous session
        initial_session = await auth_system.session_provider.create_session("anonymous")
        initial_session_id = initial_session.id
        
        # Create user and authenticate
        user = User(username="testuser", email="test@example.com")
        await auth_system.user_provider.create_user(user)
        
        # Authenticate should create NEW session, not reuse old one
        credentials = Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password"
        )
        
        auth_result = await auth_system.authenticate(credentials)
        new_session = auth_result.session
        
        # Session ID must change after authentication
        assert new_session.id != initial_session_id
        
        # Old session should be invalidated
        old_session = await auth_system.session_provider.get_session(initial_session_id)
        assert old_session is None or not old_session.is_valid
    
    async def test_session_hijacking_protection(self, auth_system):
        """Test protection against session hijacking."""
        # Create authenticated session
        user = User(username="victim", email="victim@example.com")
        await auth_system.user_provider.create_user(user)
        
        session = await auth_system.session_provider.create_session(user.id)
        
        # Simulate hijacking attempt with different IP/User-Agent
        original_context = {
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        
        hijack_context = {
            "ip_address": "10.0.0.1",  # Different IP
            "user_agent": "curl/7.68.0"  # Different User-Agent
        }
        
        # Original context should work
        assert await auth_system.session_provider.validate_session(
            session.id, original_context
        )
        
        # Hijack attempt should fail (if IP validation enabled)
        hijack_valid = await auth_system.session_provider.validate_session(
            session.id, hijack_context
        )
        
        # Should either fail validation or trigger security event
        if hijack_valid:
            # Check that security event was logged
            audit_events = await auth_system.audit_provider.get_events(
                event_type="session.suspicious_access"
            )
            assert len(audit_events) > 0

class TestTokenAttacks:
    """Test resistance to token-based attacks."""
    
    async def test_jwt_tampering_resistance(self, auth_system):
        """Test resistance to JWT token tampering."""
        # Create valid token
        user = User(username="testuser", email="test@example.com")
        valid_token = await auth_system.credential_provider.generate_token(user)
        
        # Test various tampering attempts
        tampering_attempts = [
            # Change payload
            valid_token.replace("testuser", "admin"),
            # Change signature
            valid_token[:-10] + "tampered123",
            # Change header
            "eyJhbGciOiJub25lIn0" + valid_token[valid_token.find('.'):],
            # Null byte injection
            valid_token + "\x00",
            # Different algorithm attack
            valid_token.replace("HS256", "none")
        ]
        
        for tampered_token in tampering_attempts:
            with pytest.raises((InvalidTokenError, AuthenticationError)):
                await auth_system.credential_provider.verify_token(tampered_token)
    
    async def test_token_replay_protection(self, auth_system):
        """Test protection against token replay attacks."""
        user = User(username="testuser", email="test@example.com")
        token = await auth_system.credential_provider.generate_token(user)
        
        # First use should succeed
        result1 = await auth_system.authenticate(Credentials(
            type=CredentialType.TOKEN,
            identifier="testuser",
            secret=token
        ))
        assert result1 is not None
        
        # If token blacklisting is enabled, second use should fail
        # (This tests single-use tokens if implemented)
        if auth_system.config.token_settings.get("single_use", False):
            with pytest.raises(AuthenticationError):
                await auth_system.authenticate(Credentials(
                    type=CredentialType.TOKEN,
                    identifier="testuser", 
                    secret=token
                ))

class TestPasswordAttacks:
    """Test resistance to password-based attacks."""
    
    async def test_password_brute_force_simulation(self, auth_system):
        """Simulate password brute force attacks."""
        user = User(username="target", email="target@example.com")
        await auth_system.user_provider.create_user(user)
        
        # Set strong password
        await auth_system.credential_provider.store_credentials(
            user.id, Credentials(
                type=CredentialType.PASSWORD,
                identifier="target",
                secret="StrongP@ssw0rd123!"
            )
        )
        
        # Common password attempts
        common_passwords = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master",
            "target", "target123", "admin123", "root", "toor"
        ]
        
        failed_attempts = 0
        for password in common_passwords:
            result = await auth_system.authenticate(Credentials(
                type=CredentialType.PASSWORD,
                identifier="target",
                secret=password
            ))
            
            if result is None:
                failed_attempts += 1
            else:
                pytest.fail(f"Weak password '{password}' succeeded!")
        
        # All common passwords should fail
        assert failed_attempts == len(common_passwords)
        
        # Verify audit events for failed attempts
        audit_events = await auth_system.audit_provider.get_events(
            event_type="auth.failed_login",
            user_id=user.id
        )
        assert len(audit_events) >= failed_attempts
    
    async def test_rainbow_table_resistance(self, auth_system):
        """Test resistance to rainbow table attacks via proper salting."""
        # Create multiple users with same password
        common_password = "CommonPassword123!"
        users = []
        
        for i in range(5):
            user = User(username=f"user{i}", email=f"user{i}@example.com")
            await auth_system.user_provider.create_user(user)
            await auth_system.credential_provider.store_credentials(
                user.id, Credentials(
                    type=CredentialType.PASSWORD,
                    identifier=f"user{i}",
                    secret=common_password
                )
            )
            users.append(user)
        
        # Retrieve stored password hashes
        hashes = []
        for user in users:
            stored_creds = await auth_system.credential_provider.get_credentials(
                user.id, CredentialType.PASSWORD
            )
            hashes.append(stored_creds.secret)  # This should be the hash
        
        # All hashes should be different (due to unique salts)
        assert len(set(hashes)) == len(hashes), "Password hashes are identical - salting failed!"
```

### 2. Defensive Security Testing (Blue Team)

```python
# tests/auth/security/test_defensive.py
class TestSecurityMonitoring:
    """Test security monitoring and alerting capabilities."""
    
    async def test_suspicious_activity_detection(self, auth_system):
        """Test detection of suspicious authentication patterns."""
        user = User(username="monitored", email="monitored@example.com")
        await auth_system.user_provider.create_user(user)
        
        # Simulate suspicious patterns
        suspicious_patterns = [
            # Multiple rapid login attempts
            {"count": 10, "timeframe": 1, "pattern": "rapid_attempts"},
            # Login from multiple IPs quickly
            {"ips": ["1.1.1.1", "2.2.2.2", "3.3.3.3"], "pattern": "ip_hopping"},
            # Unusual time-of-day access
            {"time": "03:00:00", "pattern": "unusual_time"}
        ]
        
        for pattern_test in suspicious_patterns:
            # Clear previous audit events
            await auth_system.audit_provider.clear()
            
            if pattern_test["pattern"] == "rapid_attempts":
                # Multiple rapid attempts
                for i in range(pattern_test["count"]):
                    await auth_system.authenticate(Credentials(
                        type=CredentialType.PASSWORD,
                        identifier="monitored",
                        secret="wrong_password"
                    ))
                    await asyncio.sleep(0.1)  # 100ms between attempts
            
            # Check for security alerts
            alerts = await auth_system.audit_provider.get_events(
                event_type="security.suspicious_activity"
            )
            
            # Should detect suspicious pattern
            assert len(alerts) > 0, f"Failed to detect {pattern_test['pattern']}"
    
    async def test_audit_integrity_protection(self, auth_system):
        """Test that audit logs cannot be tampered with."""
        user = User(username="testuser", email="test@example.com")
        
        # Perform audited action
        await auth_system.authenticate(Credentials(
            type=CredentialType.PASSWORD,
            identifier="testuser",
            secret="password"
        ))
        
        # Get audit event
        events = await auth_system.audit_provider.get_events()
        original_event = events[0]
        
        # Attempt to modify audit event
        with pytest.raises((PermissionError, SecurityError)):
            await auth_system.audit_provider.modify_event(
                original_event.id, {"event_type": "modified"}
            )
        
        # Attempt to delete audit event  
        with pytest.raises((PermissionError, SecurityError)):
            await auth_system.audit_provider.delete_event(original_event.id)
        
        # Event should remain unchanged
        current_events = await auth_system.audit_provider.get_events()
        assert len(current_events) == len(events)
        assert current_events[0].event_type == original_event.event_type

class TestInputValidationDefense:
    """Test comprehensive input validation and sanitization."""
    
    async def test_malicious_username_handling(self, auth_system):
        """Test handling of malicious usernames."""
        malicious_usernames = [
            # XSS attempts
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            
            # Path traversal
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            
            # Command injection
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& echo vulnerable",
            
            # Null bytes and control characters
            "admin\x00",
            "test\r\ninjected",
            "user\t\t\t",
            
            # Unicode attacks
            "аdmin",  # Cyrillic 'a'
            "admin\u200b",  # Zero-width space
            "admin\ufeff",  # BOM character
        ]
        
        for malicious_username in malicious_usernames:
            # Should either reject or safely sanitize
            try:
                user = User(username=malicious_username, email="test@example.com")
                await auth_system.user_provider.create_user(user)
                
                # If creation succeeds, username should be sanitized
                created_user = await auth_system.user_provider.get_user_by_username(
                    malicious_username
                )
                
                if created_user:
                    # Should not contain malicious content
                    assert not any(char in created_user.username for char in ['<', '>', '&', '"', "'", '\x00', '\r', '\n'])
                    
            except (ValueError, ValidationError):
                # Rejection is also acceptable
                pass
    
    async def test_password_policy_enforcement(self, auth_system):
        """Test password policy enforcement."""
        weak_passwords = [
            "",  # Empty
            "a",  # Too short
            "12345",  # Numbers only
            "password",  # Common word
            "Password",  # Missing numbers/symbols
            "password123",  # Missing symbols
            "PASSWORD123!",  # Missing lowercase
            "aaaaaaaaaaaa",  # Repeated characters
            "qwertyuiop",  # Keyboard pattern
            "123456789",  # Sequential numbers
        ]
        
        for weak_password in weak_passwords:
            with pytest.raises((ValidationError, WeakPasswordError)):
                await auth_system.credential_provider.store_credentials(
                    "testuser", Credentials(
                        type=CredentialType.PASSWORD,
                        identifier="testuser",
                        secret=weak_password
                    )
                )

class TestCryptographicDefense:
    """Test cryptographic security measures."""
    
    async def test_password_hash_strength(self, auth_system):
        """Test password hashing algorithm strength."""
        password = "TestPassword123!"
        
        # Store password
        await auth_system.credential_provider.store_credentials(
            "testuser", Credentials(
                type=CredentialType.PASSWORD,
                identifier="testuser", 
                secret=password
            )
        )
        
        # Retrieve stored hash
        stored_creds = await auth_system.credential_provider.get_credentials(
            "testuser", CredentialType.PASSWORD
        )
        
        password_hash = stored_creds.secret
        
        # Should use strong hashing (Argon2)
        assert password_hash.startswith("$argon2"), "Should use Argon2 hashing"
        
        # Should have sufficient cost parameters
        hash_parts = password_hash.split('$')
        assert len(hash_parts) >= 5, "Invalid hash format"
        
        # Verify it's not reversible
        assert password not in password_hash, "Password appears in hash"
        assert len(password_hash) > 50, "Hash seems too short"
    
    async def test_token_cryptographic_strength(self, auth_system):
        """Test JWT token cryptographic strength."""
        user = User(username="testuser", email="test@example.com")
        token = await auth_system.credential_provider.generate_token(user)
        
        # Should be proper JWT format
        parts = token.split('.')
        assert len(parts) == 3, "Invalid JWT format"
        
        # Header should specify secure algorithm
        import base64
        import json
        
        header = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
        assert header.get('alg') in ['HS256', 'RS256', 'ES256'], "Weak signing algorithm"
        assert header.get('alg') != 'none', "Algorithm should not be 'none'"
        
        # Token should be sufficiently long
        assert len(token) > 100, "Token seems too short"
        
        # Multiple tokens should be different
        token2 = await auth_system.credential_provider.generate_token(user)
        assert token != token2, "Tokens should be unique"
```

### 3. End-to-End Security Scenarios

```python
# tests/auth/security/test_e2e_security.py  
class TestCompleteAttackScenarios:
    """Test complete attack scenarios from start to finish."""
    
    async def test_credential_stuffing_attack(self, auth_system, http_client):
        """Simulate a credential stuffing attack."""
        # Create legitimate users
        legitimate_users = [
            ("alice", "alice@example.com", "StrongPassword1!"),
            ("bob", "bob@example.com", "SecurePass2@"),
            ("charlie", "charlie@example.com", "ComplexPwd3#")
        ]
        
        for username, email, password in legitimate_users:
            user = User(username=username, email=email)
            await auth_system.user_provider.create_user(user)
            await auth_system.credential_provider.store_credentials(
                user.id, Credentials(
                    type=CredentialType.PASSWORD,
                    identifier=username,
                    secret=password
                )
            )
        
        # Simulate credential stuffing with breached credentials
        breached_credentials = [
            ("alice", "password123"),  # Wrong password
            ("bob", "123456"),         # Wrong password  
            ("charlie", "qwerty"),     # Wrong password
            ("admin", "admin"),        # Non-existent user
            ("root", "root"),          # Non-existent user
        ]
        
        successful_auths = 0
        for username, password in breached_credentials:
            response = await http_client.post("/auth/login", json={
                "username": username,
                "password": password
            })
            
            if response.status_code == 200:
                successful_auths += 1
        
        # No breached credentials should work
        assert successful_auths == 0, "Credential stuffing attack partially succeeded"
        
        # Verify audit events were created
        failed_events = await auth_system.audit_provider.get_events(
            event_type="auth.failed_login"
        )
        assert len(failed_events) >= len(breached_credentials)
    
    async def test_session_token_theft_scenario(self, auth_system, http_client):
        """Test complete session token theft and misuse scenario."""
        # User logs in legitimately
        user = User(username="victim", email="victim@example.com")
        await auth_system.user_provider.create_user(user)
        
        login_response = await http_client.post("/auth/login", json={
            "username": "victim",
            "password": "VictimPassword123!"
        })
        
        assert login_response.status_code == 200
        session_token = login_response.cookies.get("session_token")
        
        # Attacker tries to use stolen token from different context
        attacker_headers = {
            "User-Agent": "AttackerBot/1.0",
            "X-Forwarded-For": "192.168.1.999"  # Different IP
        }
        
        # Attempt to access protected resource with stolen token
        protected_response = await http_client.get(
            "/protected/resource",
            cookies={"session_token": session_token},
            headers=attacker_headers
        )
        
        # Should either deny access or trigger security alert
        if protected_response.status_code == 200:
            # If access granted, security alert should be triggered
            security_events = await auth_system.audit_provider.get_events(
                event_type="security.suspicious_session"
            )
            assert len(security_events) > 0, "No security alert for suspicious session use"
        else:
            # Access should be denied
            assert protected_response.status_code in [401, 403]
    
    async def test_privilege_escalation_attempt(self, auth_system, http_client):
        """Test privilege escalation attack scenario."""
        # Create regular user
        regular_user = User(username="regularuser", email="regular@example.com")
        await auth_system.user_provider.create_user(regular_user)
        
        # Create admin user
        admin_user = User(username="admin", email="admin@example.com")
        await auth_system.user_provider.create_user(admin_user)
        await auth_system.user_provider.assign_role(admin_user.id, "admin")
        
        # Regular user logs in
        login_response = await http_client.post("/auth/login", json={
            "username": "regularuser",
            "password": "RegularPassword123!"
        })
        
        session_token = login_response.cookies.get("session_token")
        
        # Attempt various privilege escalation techniques
        escalation_attempts = [
            # Try to access admin endpoints
            {"method": "GET", "url": "/admin/users"},
            {"method": "POST", "url": "/admin/users", "json": {"username": "newadmin"}},
            {"method": "DELETE", "url": "/admin/users/admin"},
            
            # Try to modify own permissions
            {"method": "POST", "url": "/auth/roles", "json": {"role": "admin"}},
            {"method": "PUT", "url": "/auth/users/regularuser", "json": {"is_admin": True}},
            
            # Try parameter pollution
            {"method": "GET", "url": "/api/resource?user_id=1&user_id=admin"},
        ]
        
        blocked_attempts = 0
        for attempt in escalation_attempts:
            response = await http_client.request(
                method=attempt["method"],
                url=attempt["url"],
                json=attempt.get("json"),
                cookies={"session_token": session_token}
            )
            
            if response.status_code in [401, 403]:
                blocked_attempts += 1
        
        # All escalation attempts should be blocked
        assert blocked_attempts == len(escalation_attempts), "Some privilege escalation attempts succeeded"
        
        # Verify security events
        escalation_events = await auth_system.audit_provider.get_events(
            event_type="security.privilege_escalation_attempt"
        )
        assert len(escalation_events) > 0, "No audit events for escalation attempts"
```

### 4. Security Testing Infrastructure

```python
# tests/auth/security/conftest.py
@pytest.fixture
async def security_test_client(auth_system):
    """HTTP client configured for security testing."""
    from httpx import AsyncClient
    
    # Configure client with security testing features
    client = AsyncClient(
        timeout=30.0,  # Longer timeout for security tests
        follow_redirects=False,  # Don't follow redirects in security tests
        headers={
            "User-Agent": "SecurityTestSuite/1.0",
            "Accept": "application/json"
        }
    )
    
    yield client
    await client.aclose()

@pytest.fixture
async def malicious_payloads():
    """Common malicious payloads for testing."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin' UNION SELECT * FROM passwords --"
        ],
        "xss": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ],
        "command_injection": [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& echo vulnerable"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam"
        ]
    }

@pytest.fixture
async def attack_simulator(auth_system, security_test_client):
    """Utility for simulating various attacks."""
    class AttackSimulator:
        def __init__(self, auth_system, client):
            self.auth_system = auth_system
            self.client = client
        
        async def simulate_brute_force(self, username, password_list, delay=0.1):
            """Simulate brute force attack."""
            results = []
            for password in password_list:
                response = await self.client.post("/auth/login", json={
                    "username": username,
                    "password": password
                })
                results.append({
                    "password": password,
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                })
                await asyncio.sleep(delay)
            return results
        
        async def simulate_credential_stuffing(self, credential_pairs):
            """Simulate credential stuffing attack."""
            results = []
            for username, password in credential_pairs:
                response = await self.client.post("/auth/login", json={
                    "username": username,
                    "password": password
                })
                results.append({
                    "username": username,
                    "password": password,
                    "success": response.status_code == 200
                })
            return results
        
        async def test_injection_resistance(self, payloads, endpoint="/auth/login"):
            """Test resistance to injection attacks."""
            results = []
            for payload in payloads:
                try:
                    response = await self.client.post(endpoint, json={
                        "username": payload,
                        "password": "test"
                    })
                    results.append({
                        "payload": payload,
                        "status_code": response.status_code,
                        "vulnerable": response.status_code == 200
                    })
                except Exception as e:
                    results.append({
                        "payload": payload,
                        "error": str(e),
                        "vulnerable": False
                    })
            return results
    
    return AttackSimulator(auth_system, security_test_client)
```

### 5. Security Test Configuration

```python
# tests/auth/security/security_config.py
SECURITY_TEST_CONFIG = {
    "timing_tests": {
        "max_variance_percent": 20,  # Maximum timing variance allowed
        "sample_size": 10,           # Number of timing samples
        "timeout_seconds": 5         # Maximum time per operation
    },
    
    "brute_force_tests": {
        "common_passwords": [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        ],
        "attack_patterns": {
            "rapid_fire": {"count": 20, "delay": 0.1},
            "slow_burn": {"count": 100, "delay": 1.0},
            "burst": {"count": 5, "delay": 0.01}
        }
    },
    
    "injection_tests": {
        "sql_payloads": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin' UNION SELECT password FROM users --",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ],
        "nosql_payloads": [
            {"$ne": None},
            {"$regex": ".*"},
            {"$where": "this.username == 'admin'"}
        ]
    },
    
    "session_tests": {
        "hijack_scenarios": [
            {"ip_change": True, "user_agent_change": False},
            {"ip_change": False, "user_agent_change": True},
            {"ip_change": True, "user_agent_change": True}
        ]
    }
}
```
            
            start_time = time.time()
            await auth_system.authenticate(credentials)
            end_time = time.time()
            
            times.append(end_time - start_time)
        
        # Times should be similar (within reasonable variance)
        time_diff = abs(times[0] - times[1])
        assert time_diff < 0.1  # 100ms tolerance
    
    async def test_session_fixation_protection(self, auth_system):
        """Test protection against session fixation attacks."""
        # Create initial session
        initial_session = await auth_system.session_provider.create_session("temp_user")
        initial_session_id = initial_session.id
        
        # Authenticate with real credentials
        credentials = Credentials(type=CredentialType.PASSWORD, identifier="testuser", secret="password")
        auth_session = await auth_system.authenticate(credentials)
        
        # Session ID should be different after authentication
        assert auth_session.id != initial_session_id
        
        # Old session should be invalid
        old_session = await auth_system.validate_session(initial_session_id)
        assert old_session is None
```

### 2. Audit Compliance Testing

```python
# tests/auth/security/test_audit_compliance.py
class TestAuditCompliance:
    async def test_complete_audit_trail(self, auth_system):
        """Test that all security operations are audited."""
        audit_provider = auth_system.audit_provider
        
        # Clear audit log
        audit_provider.clear()
        
        # Perform authentication flow
        user = await auth_system.user_provider.create_user("testuser")
        credentials = Credentials(type=CredentialType.PASSWORD, identifier="testuser", secret="password")
        await auth_system.credential_provider.create_credentials(user.id, credentials)
        session = await auth_system.authenticate(credentials)
        
        # Check audit events
        events = await audit_provider.get_events()
        
        expected_events = [
            AuditEventType.USER_CREATE,
            AuditEventType.CREDENTIAL_CREATE,
            AuditEventType.AUTH_ATTEMPT,
            AuditEventType.AUTH_SUCCESS,
            AuditEventType.SESSION_CREATE
        ]
        
        actual_event_types = [event.event_type for event in events]
        
        for expected_event in expected_events:
            assert expected_event in actual_event_types
    
    async def test_audit_event_integrity(self, auth_system):
        """Test audit event integrity and immutability."""
        audit_provider = auth_system.audit_provider
        
        # Perform audited operation
        await auth_system.user_provider.create_user("testuser")
        
        events = await audit_provider.get_events()
        assert len(events) == 1
        
        original_event = events[0]
        
        # Try to modify audit event (should fail or be detected)
        with pytest.raises(AuditIntegrityError):
            await audit_provider.modify_event(original_event.id, {"user_id": "hacker"})
```

## Performance Testing

### 1. Load Testing

```python
# tests/auth/performance/test_load.py
class TestPerformanceUnderLoad:
    @pytest.mark.performance
    async def test_concurrent_authentication(self, auth_system):
        """Test authentication performance under concurrent load."""
        # Set up test users
        users = []
        for i in range(100):
            user = await auth_system.user_provider.create_user(f"user{i}")
            credentials = Credentials(type=CredentialType.PASSWORD, identifier=f"user{i}", secret="password")
            await auth_system.credential_provider.create_credentials(user.id, credentials)
            users.append((user, credentials))
        
        # Concurrent authentication
        async def authenticate_user(user, credentials):
            return await auth_system.authenticate(credentials)
        
        start_time = time.time()
        
        tasks = [authenticate_user(user, creds) for user, creds in users]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        
        # Verify all authentications succeeded
        assert all(session is not None for session in results)
        
        # Performance assertion (should handle 100 concurrent auths in reasonable time)
        total_time = end_time - start_time
        assert total_time < 5.0  # 5 seconds max
        
        # Average time per authentication
        avg_time = total_time / len(users)
        assert avg_time < 0.1  # 100ms average
    
    @pytest.mark.performance
    async def test_session_lookup_performance(self, auth_system):
        """Test session lookup performance with many sessions."""
        # Create many sessions
        sessions = []
        for i in range(1000):
            session = await auth_system.session_provider.create_session(f"user{i}")
            sessions.append(session)
        
        # Test lookup performance
        start_time = time.time()
        
        # Random session lookups
        lookup_tasks = []
        for _ in range(100):
            random_session = random.choice(sessions)
            lookup_tasks.append(auth_system.validate_session(random_session.id))
        
        results = await asyncio.gather(*lookup_tasks)
        
        end_time = time.time()
        
        # Verify lookups succeeded
        assert all(session is not None for session in results)
        
        # Performance assertion
        total_time = end_time - start_time
        avg_lookup_time = total_time / len(lookup_tasks)
        assert avg_lookup_time < 0.01  # 10ms average lookup time
```

## Test Utilities and Fixtures

### 1. Test Data Factories

```python
# tests/auth/factories.py
class UserFactory:
    @staticmethod
    def create_user(**kwargs) -> User:
        defaults = {
            "id": str(uuid.uuid4()),
            "username": f"user_{random.randint(1000, 9999)}",
            "email": f"test_{random.randint(1000, 9999)}@example.com",
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.utcnow(),
            "last_login": None,
            "metadata": {}
        }
        defaults.update(kwargs)
        return User(**defaults)

class CredentialsFactory:
    @staticmethod
    def create_password_credentials(**kwargs) -> Credentials:
        defaults = {
            "type": CredentialType.PASSWORD,
            "identifier": f"user_{random.randint(1000, 9999)}",
            "secret": "password123",
            "metadata": {}
        }
        defaults.update(kwargs)
        return Credentials(**defaults)

class SessionFactory:
    @staticmethod
    def create_session(**kwargs) -> Session:
        now = datetime.utcnow()
        defaults = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "created_at": now,
            "expires_at": now + timedelta(hours=8),
            "last_accessed": now,
            "ip_address": "192.168.1.100",
            "user_agent": "test-client/1.0",
            "metadata": {}
        }
        defaults.update(kwargs)
        return Session(**defaults)
```

### 2. Mock Providers

```python
# tests/auth/mocks.py
class MockAuditProvider(AuditProvider):
    def __init__(self, config: Dict[str, Any] = None, container: Container = None):
        self.config = config or {}
        self.container = container
        self.events = []
    
    async def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)
    
    async def query_events(self, **kwargs) -> List[AuditEvent]:
        return self.events
    
    def clear(self):
        self.events.clear()
    
    async def get_events(self) -> List[AuditEvent]:
        return self.events.copy()

class MockPolicyProvider(PolicyProvider):
    def __init__(self, config: Dict[str, Any] = None, container: Container = None):
        self.config = config or {}
        self.container = container
        self.permissions = {}
        self.roles = {}
    
    async def evaluate_permission(self, user: User, permission: Permission, context=None) -> PolicyEvaluation:
        user_permissions = self.permissions.get(user.id, set())
        if permission in user_permissions:
            return PolicyEvaluation(PolicyResult.ALLOW, "permission_granted")
        return PolicyEvaluation(PolicyResult.DENY, "permission_denied")
    
    def grant_permission(self, user_id: str, permission: Permission):
        if user_id not in self.permissions:
            self.permissions[user_id] = set()
        self.permissions[user_id].add(permission)
```

This comprehensive testing strategy ensures:
- **Complete Coverage**: All components tested at multiple levels
- **Security Focus**: Dedicated security and penetration testing
- **Performance Validation**: Load testing and performance benchmarks
- **Compliance**: Audit trail verification and compliance testing
- **Maintainability**: Well-structured test utilities and factories
- **Reliability**: Integration testing with real dependencies
- **Documentation**: Tests serve as living documentation of expected behavior