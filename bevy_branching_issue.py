#!/usr/bin/env python3
"""
Minimal reproduction of Bevy container branching issue.

This script demonstrates that dependencies registered in a parent container
are not accessible from a branched container, even though the documentation
suggests they should be.

Expected behavior: Branched containers should inherit instance registrations
from their parent containers.

Actual behavior: DependencyResolutionError is raised when trying to access
parent container dependencies from a branched container.
"""

import asyncio

from bevy import Inject, get_registry, injectable


class ParentService:
    def __init__(self, value: str):
        self.value = value


class ChildService:
    def __init__(self, name: str):
        self.name = name


@injectable
async def handler_function(parent: Inject[ParentService], child: Inject[ChildService]):
    """Function that requires both parent and child dependencies."""
    return f"Parent: {parent.value}, Child: {child.name}"


async def main():
    print("=== Bevy Container Branching Issue Reproduction ===\n")

    # Create parent container and register a service
    registry = get_registry()
    parent_container = registry.create_container()
    parent_service = ParentService("from_parent")
    parent_container.add(ParentService, parent_service)

    print("✓ Registered ParentService in parent container")

    # Test: Call function directly with parent container (should work)
    try:
        # Add the child service to parent container for this test
        child_service = ChildService("test_child")
        parent_container.add(ChildService, child_service)

        result = await parent_container.call(handler_function)
        print(f"✓ Direct call with parent container: {result}")

        # Remove child service for next test
        del parent_container.instances[ChildService]

    except Exception as e:
        print(f"✗ Direct call with parent container failed: {e}")

    # Test: Call function with branched container (this is where the issue occurs)
    print("\n--- Testing branched container behavior ---")

    try:
        with parent_container.branch() as child_container:
            print("✓ Created branched container")

            # Register a new service only in the child container
            child_service = ChildService("from_child")
            child_container.add(ChildService, child_service)
            print("✓ Registered ChildService in child container")

            # This should work because:
            # - ChildService is in child_container
            # - ParentService should be inherited from parent_container
            # But it fails with DependencyResolutionError
            result = await child_container.call(handler_function)
            print(f"✓ SUCCESS: Call with branched container: {result}")

    except Exception as e:
        print(f"✗ ISSUE: Call with branched container failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Show what's actually in each container
        print("\n--- Container Contents Debug ---")
        print(f"Parent container instances: {list(parent_container.instances.keys())}")
        print(f"Child container instances: {list(child_container.instances.keys())}")

        # Test if we can manually get the parent service from child container
        try:
            retrieved_parent = child_container.get(ParentService)
            print(
                f"✓ Can manually get ParentService from child: {retrieved_parent.value}"
            )
        except Exception as get_error:
            print(f"✗ Cannot manually get ParentService from child: {get_error}")


if __name__ == "__main__":
    asyncio.run(main())
