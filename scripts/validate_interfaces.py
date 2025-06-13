#!/usr/bin/env python3
"""
Interface compliance validation script for authentication providers.

This script validates that all concrete provider implementations properly
implement their abstract base class interfaces. It's designed to be run
in CI/CD pipelines to catch interface compliance issues early.
"""

import sys
import traceback
from typing import Type, get_type_hints
import inspect
from abc import ABC
from pathlib import Path

# Add the project root to the path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from bevy import Container, get_registry
    from serv.auth.providers.credential import CredentialProvider
    from serv.auth.providers.session import SessionProvider
    from serv.auth.providers.user import UserProvider
    from serv.auth.providers.audit import AuditProvider
    from serv.bundled.auth.memory.credential import MemoryCredentialProvider
    from serv.bundled.auth.memory.session import MemorySessionProvider
    from serv.bundled.auth.memory.user import MemoryUserProvider
    from serv.bundled.auth.memory.audit import MemoryAuditProvider
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    sys.exit(1)


def validate_abc_compliance(provider_class: Type, abstract_class: Type) -> list[str]:
    """
    Validate that a provider class properly implements all abstract methods.
    
    Returns a list of compliance issues, empty list if compliant.
    """
    issues = []
    
    # Get all abstract methods from the abstract class
    abstract_methods = set()
    for cls in abstract_class.__mro__:
        if hasattr(cls, '__abstractmethods__'):
            abstract_methods.update(cls.__abstractmethods__)
    
    # Check each abstract method
    for method_name in abstract_methods:
        if not hasattr(provider_class, method_name):
            issues.append(f"Missing abstract method: {method_name}")
            continue
            
        # Get method from provider and abstract class
        provider_method = getattr(provider_class, method_name)
        abstract_method = getattr(abstract_class, method_name)
        
        # Check if it's still abstract (not implemented)
        if hasattr(provider_method, '__isabstractmethod__') and provider_method.__isabstractmethod__:
            issues.append(f"Abstract method not implemented: {method_name}")
            continue
        
        # Validate method signature compatibility
        try:
            provider_sig = inspect.signature(provider_method)
            abstract_sig = inspect.signature(abstract_method)
            
            # Check parameter count and names
            provider_params = list(provider_sig.parameters.keys())
            abstract_params = list(abstract_sig.parameters.keys())
            
            if len(provider_params) != len(abstract_params):
                issues.append(f"Method {method_name}: parameter count mismatch")
                continue
            
            # Check parameter types if type hints are available
            try:
                provider_hints = get_type_hints(provider_method)
                abstract_hints = get_type_hints(abstract_method)
                
                for param_name in abstract_params:
                    if param_name in provider_hints and param_name in abstract_hints:
                        if provider_hints[param_name] != abstract_hints[param_name]:
                            issues.append(f"Method {method_name}: parameter '{param_name}' type mismatch")
                
                # Check return type
                if 'return' in provider_hints and 'return' in abstract_hints:
                    if provider_hints['return'] != abstract_hints['return']:
                        issues.append(f"Method {method_name}: return type mismatch")
                        
            except (NameError, AttributeError, TypeError):
                # Type hints might not be available or might use complex types
                # Skip type checking in these cases
                pass
                
        except (ValueError, TypeError) as e:
            issues.append(f"Method {method_name}: signature inspection failed: {e}")
    
    return issues


def test_provider_instantiation(provider_class: Type, config: dict) -> list[str]:
    """
    Test that a provider can be instantiated without errors.
    
    Returns a list of instantiation issues, empty list if successful.
    """
    issues = []
    
    try:
        container = Container(get_registry())
        instance = provider_class(config, container)
        
        # Basic validation that the instance is the right type
        if not isinstance(instance, provider_class):
            issues.append(f"Instantiation returned wrong type: {type(instance)}")
            
    except TypeError as e:
        if "abstract methods" in str(e):
            issues.append(f"Cannot instantiate due to abstract methods: {e}")
        else:
            issues.append(f"Instantiation failed with TypeError: {e}")
    except Exception as e:
        issues.append(f"Instantiation failed with {type(e).__name__}: {e}")
    
    return issues


def validate_provider(provider_class: Type, abstract_class: Type, provider_name: str) -> bool:
    """
    Validate a single provider implementation.
    
    Returns True if validation passes, False otherwise.
    """
    print(f"\n🔍 Validating {provider_name}...")
    
    # Check ABC compliance
    abc_issues = validate_abc_compliance(provider_class, abstract_class)
    
    # Test instantiation
    test_config = {
        "cleanup_interval": 0.1,
        "max_login_attempts": 3,
        "retention_days": 90,
    }
    instantiation_issues = test_provider_instantiation(provider_class, test_config)
    
    # Report results
    all_issues = abc_issues + instantiation_issues
    
    if not all_issues:
        print(f"✅ {provider_name} passed all validation checks")
        return True
    else:
        print(f"❌ {provider_name} failed validation:")
        for issue in all_issues:
            print(f"   • {issue}")
        return False


def main():
    """Main validation routine."""
    print("🚀 Starting authentication provider interface validation...")
    
    # Define provider mappings
    providers_to_validate = [
        (MemoryCredentialProvider, CredentialProvider, "MemoryCredentialProvider"),
        (MemorySessionProvider, SessionProvider, "MemorySessionProvider"),
        (MemoryUserProvider, UserProvider, "MemoryUserProvider"),
        (MemoryAuditProvider, AuditProvider, "MemoryAuditProvider"),
    ]
    
    validation_passed = True
    
    for provider_class, abstract_class, provider_name in providers_to_validate:
        try:
            if not validate_provider(provider_class, abstract_class, provider_name):
                validation_passed = False
        except Exception as e:
            print(f"❌ {provider_name} validation crashed: {e}")
            traceback.print_exc()
            validation_passed = False
    
    print(f"\n{'='*60}")
    
    if validation_passed:
        print("🎉 All provider implementations passed interface validation!")
        print("✅ The authentication system maintains proper polymorphic behavior.")
        sys.exit(0)
    else:
        print("💥 Some provider implementations failed interface validation!")
        print("❌ Please fix the reported issues to maintain polymorphic behavior.")
        sys.exit(1)


if __name__ == "__main__":
    main()