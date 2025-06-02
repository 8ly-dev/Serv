# Logic Errors

## Problem Description

The Serv codebase contains several logical errors that could cause runtime issues or unexpected behavior. These are critical bugs that need immediate fixing.

### Critical Logic Errors Found

**1. Extension Config File Duplication** (serv/extensions/loader.py:172-183)
```python
# LOGIC ERROR: Duplicate assignment overwrites the first
extension_config = path / "extension.yaml"
extension_config = path / "extension.yaml"  # This overwrites the previous line!

if extension_config.exists():
    config_file = extension_config
elif extension_config.exists():  # This condition will NEVER be True
    config_file = extension_config
```

**2. Parameter Assignment Logic Error** (serv/app.py:248-250)
```python
# LOGIC ERROR: This expression always evaluates to extension_dir
actual_extension_dir = extension_dir if extension_dir is None else extension_dir
# Should probably be:
# actual_extension_dir = extension_dir if extension_dir is not None else default_dir
```

**3. Duplicate Pattern Match Cases** (serv/extensions/loader.py:490-494)
```python
# LOGIC ERROR: Duplicate cases in pattern matching
case {"extension": str() as extension, "settings": dict() as settings}:
    return extension, settings
case {"extension": str() as extension}:
    return extension, {}
# These same patterns are repeated below, making some code unreachable
```

**4. Search Loop Logic Error** (serv/extensions/extensions.py:156-163)
```python
def search_for_extension_directory(path: Path) -> Path | None:
    while path.name:
        # LOGIC ERROR: Same condition checked twice
        if (path / "extension.yaml").exists() or (path / "extension.yaml").exists():
            return path
        path = path.parent
    # LOGIC ERROR: Function signature says returns Path | None but always raises
    raise Exception("Extension directory not found")
```

## Impact Assessment

- **Severity**: 🔴 **HIGH** (Runtime failures, incorrect behavior)
- **Reliability**: **CRITICAL** (Code doesn't work as intended)
- **User Impact**: **HIGH** (Extension loading failures, crashes)
- **Debug Difficulty**: **HIGH** (Logic errors are hard to trace)

## Recommendations

### Fix 1: Extension Config File Loading
**Effort**: Low | **Impact**: High

```python
# BEFORE (broken):
extension_config = path / "extension.yaml"
extension_config = path / "extension.yaml"

if extension_config.exists():
    config_file = extension_config
elif extension_config.exists():
    config_file = extension_config

# AFTER (fixed):
extension_yaml = path / "extension.yaml"
plugin_yaml = path / "plugin.yaml"  # Legacy support

if extension_yaml.exists():
    config_file = extension_yaml
elif plugin_yaml.exists():
    config_file = plugin_yaml
else:
    raise FileNotFoundError(f"No extension config found in {path}")
```

### Fix 2: Parameter Assignment Logic
**Effort**: Low | **Impact**: Medium

```python
# BEFORE (broken):
actual_extension_dir = extension_dir if extension_dir is None else extension_dir

# AFTER (fixed - need to understand intended logic):
# Option A: Use default if None
actual_extension_dir = extension_dir if extension_dir is not None else Path.cwd() / "extensions"

# Option B: Remove line entirely if not needed
# Just use extension_dir directly
```

### Fix 3: Remove Duplicate Pattern Cases
**Effort**: Low | **Impact**: Low

```python
# BEFORE (broken):
match config_data:
    case {"extension": str() as extension, "settings": dict() as settings}:
        return extension, settings
    case {"extension": str() as extension}:
        return extension, {}
    case {"extension": str() as extension, "settings": dict() as settings}:  # DUPLICATE
        return extension, settings
    case {"extension": str() as extension}:  # DUPLICATE
        return extension, {}

# AFTER (fixed):
match config_data:
    case {"extension": str() as extension, "settings": dict() as settings}:
        return extension, settings
    case {"extension": str() as extension}:
        return extension, {}
    case _:
        raise ValueError(f"Invalid extension config format: {config_data}")
```

### Fix 4: Search Function Logic
**Effort**: Low | **Impact**: Medium

```python
# BEFORE (broken):
def search_for_extension_directory(path: Path) -> Path | None:
    while path.name:
        if (path / "extension.yaml").exists() or (path / "extension.yaml").exists():
            return path
        path = path.parent
    raise Exception("Extension directory not found")

# AFTER (fixed):
def search_for_extension_directory(path: Path) -> Path | None:
    """Search for extension directory starting from path and going up."""
    current = path
    while current.name:  # Stop at root directory
        if (current / "extension.yaml").exists() or (current / "plugin.yaml").exists():
            return current
        current = current.parent
    return None  # Return None as signature indicates, don't raise
```

## Action Checklist

### Phase 1: Critical Fixes (Day 1)
- [ ] Fix extension config file duplication logic
- [ ] Investigate and fix parameter assignment logic error
- [ ] Remove duplicate pattern match cases
- [ ] Fix search function logic and return type consistency

### Phase 2: Testing (Day 2)
- [ ] Add unit tests for all fixed logic
- [ ] Test extension loading with fixed logic
- [ ] Verify no regressions in existing functionality
- [ ] Add integration tests for edge cases

### Phase 3: Prevention (Day 3)
- [ ] Add static analysis rules to catch similar issues
- [ ] Set up automated testing for logic errors
- [ ] Document code review checklist for logic errors
- [ ] Add linting rules for common patterns

### Testing Strategy

**Unit Tests for Fixes**:
```python
def test_extension_config_loading():
    """Test extension config loading logic."""
    # Test extension.yaml exists
    temp_dir = tmp_path / "test_extension"
    temp_dir.mkdir()
    (temp_dir / "extension.yaml").write_text("name: test")
    
    config_file = find_extension_config(temp_dir)
    assert config_file == temp_dir / "extension.yaml"
    
    # Test plugin.yaml fallback
    (temp_dir / "extension.yaml").unlink()
    (temp_dir / "plugin.yaml").write_text("name: test")
    
    config_file = find_extension_config(temp_dir)
    assert config_file == temp_dir / "plugin.yaml"
    
    # Test no config file
    (temp_dir / "plugin.yaml").unlink()
    
    with pytest.raises(FileNotFoundError):
        find_extension_config(temp_dir)

def test_search_extension_directory():
    """Test extension directory search logic."""
    # Create nested directory structure
    base = tmp_path / "project" / "src" / "module"
    base.mkdir(parents=True)
    
    # Put extension.yaml in parent
    (tmp_path / "project" / "extension.yaml").write_text("name: test")
    
    # Search should find it
    found = search_for_extension_directory(base)
    assert found == tmp_path / "project"
    
    # Test not found case
    (tmp_path / "project" / "extension.yaml").unlink()
    found = search_for_extension_directory(base)
    assert found is None

def test_pattern_matching_logic():
    """Test extension config pattern matching."""
    # Test with settings
    config = {"extension": "test.module", "settings": {"key": "value"}}
    extension, settings = parse_extension_config(config)
    assert extension == "test.module"
    assert settings == {"key": "value"}
    
    # Test without settings
    config = {"extension": "test.module"}
    extension, settings = parse_extension_config(config)
    assert extension == "test.module"
    assert settings == {}
    
    # Test invalid config
    with pytest.raises(ValueError):
        parse_extension_config({"invalid": "config"})
```

**Integration Tests**:
```python
def test_extension_loading_with_fixes():
    """Test that extension loading works with logic fixes."""
    app = App()
    
    # Create test extension
    ext_dir = tmp_path / "test_ext"
    ext_dir.mkdir()
    
    # Test both config file types work
    for config_name in ["extension.yaml", "plugin.yaml"]:
        config_file = ext_dir / config_name
        config_file.write_text("""
        name: test_extension
        listeners:
          - "test_ext.main.TestExtension"
        """)
        
        # Should load successfully
        extension = load_extension_from_path(ext_dir)
        assert extension is not None
        
        config_file.unlink()
```

### Static Analysis Rules

**Add to ruff configuration**:
```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings  
    "F",   # Pyflakes
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "SIM", # flake8-simplify
    "RET", # flake8-return
]

# Specifically catch logic errors
[tool.ruff.lint.per-file-ignores]
# Allow duplicate code in tests
"tests/*" = ["UP"]
```

**Custom Logic Error Detection**:
```python
# scripts/detect_logic_errors.py
import ast
import sys

class LogicErrorDetector(ast.NodeVisitor):
    def visit_Compare(self, node):
        """Detect duplicate comparisons like: x or x"""
        if isinstance(node.ops[0], ast.Or):
            # Check if same variable compared twice
            pass
    
    def visit_Assign(self, node):
        """Detect assignments like: x = x if x is None else x"""
        # Check for tautological assignments
        pass

# Run with: python scripts/detect_logic_errors.py serv/
```

### Documentation Updates

- [ ] Add code review checklist for logic errors
- [ ] Document common logic error patterns to avoid
- [ ] Add unit testing requirements for all logic changes
- [ ] Create debugging guide for logic errors

### Long-term Prevention

1. **Mandatory Code Review**: All logic changes require review
2. **Automated Testing**: Logic errors caught by comprehensive tests
3. **Static Analysis**: Automated detection of common logic patterns
4. **Documentation**: Clear requirements and edge case handling