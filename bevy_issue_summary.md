# Bevy Container Branching Issue

## Summary

There is an inconsistency in how Bevy's container branching handles dependency resolution during function calls vs manual dependency retrieval.

## Expected Behavior

When calling `container.call(function)` on a branched container, the dependency injection should resolve dependencies from both:
1. The current (child) container
2. The parent container hierarchy

This is the logical expectation since `container.get(Type)` successfully retrieves dependencies from parent containers.

## Actual Behavior

- ✅ `child_container.get(ParentService)` works correctly
- ❌ `child_container.call(function_requiring_ParentService)` fails with `DependencyResolutionError`

## Impact

This inconsistency forces users to implement workarounds like manually re-registering parent dependencies in child containers, which defeats the purpose of container inheritance.

## Reproduction

Run `python bevy_branching_issue.py` to see the issue demonstrated.

## Expected Output vs Actual Output

**Expected:**
```
✓ SUCCESS: Call with branched container: Parent: from_parent, Child: from_child
```

**Actual:**
```
✗ ISSUE: Call with branched container failed: Cannot resolve dependency ParentService for parameter 'parent'
```

## Root Cause Analysis

The issue appears to be in the dependency resolution logic used by `Container.call()`. While `Container.get()` properly traverses the parent container hierarchy, the dependency injection mechanism in `Container.call()` only looks at the current container's instances.

## Suggested Fix

The dependency resolution in `Container.call()` should use the same traversal logic as `Container.get()` to check parent containers when a dependency is not found in the current container.