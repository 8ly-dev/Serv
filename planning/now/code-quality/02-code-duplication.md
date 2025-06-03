# Code Duplication

## Problem Description

The Serv codebase contains several instances of code duplication that violate the DRY (Don't Repeat Yourself) principle. This duplication increases maintenance burden, introduces inconsistencies, and makes the codebase harder to modify.

### Identified Code Duplication

**1. Traceback Formatting Duplication** (serv/app.py)
```python
# Location 1: Lines 611-614
tb_lines = traceback.format_exception(
    type(error), error, error.__traceback__
)
full_traceback = "".join(tb_lines)

# Location 2: Lines 634-635  
else:
    full_traceback = "".join(traceback.format_exception(error))
```

**2. Extension File Checking** (serv/extensions/loader.py)
```python
# Multiple locations check for extension files similarly
if (path / "extension.yaml").exists():
    config_file = path / "extension.yaml"
elif (path / "plugin.yaml").exists():  # Legacy support
    config_file = path / "plugin.yaml"

# This pattern is repeated in multiple functions
```

**3. Import String Parsing** (Multiple files)
```python
# serv/extensions/importer.py
def import_from_string(import_string: str):
    module_path, attr_name = import_string.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)

# Similar logic exists in other files for CLI and routing
```

**4. Error Message Construction** (serv/routes.py)
```python
# Pattern repeated multiple times for different error types
error_msg = (
    f"Handler error details:\n"
    f"  Handler: {handler_class}.{handler_method_name}()\n"
    f"  Module: {handler_module}\n"
    f"  File: {handler_file}\n"
    f"  Line: {handler_line}\n"
    # ... more fields
)
```

**5. Header Case Handling** (Multiple files)
```python
# Pattern for case-insensitive header lookup repeated
header_value = request.headers.get(name) or request.headers.get(name.lower())
```

## Impact Assessment

- **Severity**: 🟡 **MEDIUM** (Maintainability issue)
- **Maintenance Burden**: **HIGH** (Changes need to be made in multiple places)
- **Bug Risk**: **MEDIUM** (Inconsistent fixes across duplicated code)
- **Code Quality**: **POOR** (Violates DRY principle)

## Recommendations

### Fix 1: Extract Traceback Utility
**Effort**: Low | **Impact**: Medium

```python
# serv/utils/diagnostics.py - New utility module
from typing import Type
import traceback

class TracebackFormatter:
    @staticmethod
    def format_exception(error: Exception, include_context: bool = True) -> str:
        """Format exception with consistent formatting."""
        if include_context:
            tb_lines = traceback.format_exception(
                type(error), error, error.__traceback__
            )
        else:
            tb_lines = traceback.format_exception_only(type(error), error)
        
        return "".join(tb_lines)
    
    @staticmethod
    def format_exception_for_display(error: Exception, 
                                   handler_info: dict = None) -> str:
        """Format exception for user display."""
        base_traceback = TracebackFormatter.format_exception(error)
        
        if handler_info:
            context_info = "\n".join([
                f"  {key}: {value}" for key, value in handler_info.items()
            ])
            return f"{base_traceback}\nHandler Context:\n{context_info}"
        
        return base_traceback

# Usage in serv/app.py
from serv.utils.diagnostics import TracebackFormatter

# Replace both duplicated instances with:
full_traceback = TracebackFormatter.format_exception(error)
```

### Fix 2: Extension File Discovery Utility
**Effort**: Low | **Impact**: Medium

```python
# serv/extensions/utils.py - New utility for extension operations
from pathlib import Path
from typing import Optional

class ExtensionFileLocator:
    """Utility for locating extension configuration files."""
    
    CONFIG_FILENAMES = ["extension.yaml", "plugin.yaml"]  # Order matters
    
    @classmethod
    def find_config_file(cls, path: Path) -> Optional[Path]:
        """Find extension config file in directory."""
        for filename in cls.CONFIG_FILENAMES:
            config_file = path / filename
            if config_file.exists():
                return config_file
        return None
    
    @classmethod
    def search_for_extension_directory(cls, start_path: Path) -> Optional[Path]:
        """Search for extension directory from start_path upward."""
        current = start_path
        while current.name:
            if cls.find_config_file(current):
                return current
            current = current.parent
        return None

# Replace all duplicated file checking with:
config_file = ExtensionFileLocator.find_config_file(path)
if not config_file:
    raise FileNotFoundError(f"No extension config found in {path}")
```

### Fix 3: Import String Utility
**Effort**: Low | **Impact**: Medium

```python
# serv/utils/imports.py - Centralized import utilities
import importlib
from typing import Any, Tuple

class ImportUtils:
    """Utilities for dynamic imports."""
    
    @staticmethod
    def parse_import_string(import_string: str) -> Tuple[str, str]:
        """Parse 'module.path.attribute' into module and attribute."""
        if "." not in import_string:
            raise ValueError(f"Invalid import string: {import_string}")
        
        module_path, attr_name = import_string.rsplit(".", 1)
        return module_path, attr_name
    
    @staticmethod
    def import_from_string(import_string: str) -> Any:
        """Import object from string like 'module.path.ClassName'."""
        module_path, attr_name = ImportUtils.parse_import_string(import_string)
        
        try:
            module = importlib.import_module(module_path)
            return getattr(module, attr_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import {import_string}: {e}") from e
    
    @staticmethod
    def validate_import_string(import_string: str) -> bool:
        """Validate import string without actually importing."""
        try:
            ImportUtils.parse_import_string(import_string)
            return True
        except ValueError:
            return False

# Replace all import string parsing with:
from serv.utils.imports import ImportUtils
obj = ImportUtils.import_from_string("my.module.Class")
```

### Fix 4: Error Message Builder
**Effort**: Medium | **Impact**: Medium

```python
# serv/utils/errors.py - Structured error message building
from typing import Dict, Any, Optional
import inspect

class ErrorMessageBuilder:
    """Builder for consistent error messages."""
    
    def __init__(self, error_type: str):
        self.error_type = error_type
        self.context: Dict[str, Any] = {}
    
    def add_handler_context(self, handler: Any) -> 'ErrorMessageBuilder':
        """Add handler context information."""
        try:
            self.context.update({
                "Handler": f"{type(handler).__name__}.{handler.__name__}()",
                "Module": getattr(handler, '__module__', 'unknown'),
                "File": inspect.getsourcefile(handler) or 'unknown',
                "Line": inspect.getsourcelines(handler)[1] if inspect.getsourcelines(handler) else 'unknown'
            })
        except Exception:
            self.context["Handler"] = "unknown"
        return self
    
    def add_request_context(self, request: Any) -> 'ErrorMessageBuilder':
        """Add request context information."""
        self.context.update({
            "Method": getattr(request, 'method', 'unknown'),
            "Path": getattr(request, 'path', 'unknown'),
            "Headers": dict(getattr(request, 'headers', {}))
        })
        return self
    
    def add_custom_context(self, **kwargs) -> 'ErrorMessageBuilder':
        """Add custom context fields."""
        self.context.update(kwargs)
        return self
    
    def build(self, base_message: str) -> str:
        """Build the complete error message."""
        context_lines = [
            f"  {key}: {value}" for key, value in self.context.items()
        ]
        context_str = "\n".join(context_lines)
        
        return f"{self.error_type}: {base_message}\n\nContext:\n{context_str}"

# Usage in serv/routes.py
from serv.utils.errors import ErrorMessageBuilder

# Replace duplicated error message construction with:
error_msg = (ErrorMessageBuilder("Parameter Resolution Error")
            .add_handler_context(handler)
            .add_request_context(request)
            .add_custom_context(
                parameter=param_name,
                expected_type=param_annotation
            )
            .build("Required parameter could not be resolved"))
```

### Fix 5: Header Utilities
**Effort**: Low | **Impact**: Low

```python
# serv/utils/http.py - HTTP utilities
from typing import Optional, Dict, Any

class HeaderUtils:
    """Utilities for HTTP header handling."""
    
    @staticmethod
    def get_header_case_insensitive(headers: Dict[str, str], 
                                  name: str) -> Optional[str]:
        """Get header value with case-insensitive lookup."""
        # Try exact match first (most common case)
        if name in headers:
            return headers[name]
        
        # Try lowercase match
        name_lower = name.lower()
        if name_lower in headers:
            return headers[name_lower]
        
        # Try case-insensitive search
        for key, value in headers.items():
            if key.lower() == name_lower:
                return value
        
        return None
    
    @staticmethod
    def normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Normalize header names to lowercase."""
        return {key.lower(): value for key, value in headers.items()}

# Replace all header case handling with:
from serv.utils.http import HeaderUtils
header_value = HeaderUtils.get_header_case_insensitive(request.headers, header_name)
```

## Action Checklist

### Phase 1: Create Utility Modules (Week 1)
- [ ] Create `serv/utils/` package structure
- [ ] Implement TracebackFormatter utility
- [ ] Implement ExtensionFileLocator utility
- [ ] Implement ImportUtils utility
- [ ] Implement ErrorMessageBuilder utility
- [ ] Implement HeaderUtils utility

### Phase 2: Replace Duplicated Code (Week 1)
- [ ] Replace traceback formatting duplication in app.py
- [ ] Replace extension file checking in loader.py
- [ ] Replace import string parsing across modules
- [ ] Replace error message construction in routes.py
- [ ] Replace header case handling across modules

### Phase 3: Testing & Validation (Week 1)
- [ ] Add comprehensive tests for all utility functions
- [ ] Verify no functionality regressions
- [ ] Test edge cases for all utilities
- [ ] Add integration tests

### Phase 4: Documentation (Week 1)
- [ ] Document new utility modules
- [ ] Add usage examples for utilities
- [ ] Update code review guidelines to prevent duplication
- [ ] Add automated duplication detection

### New File Structure

```
serv/utils/
├── __init__.py
├── diagnostics.py      # TracebackFormatter
├── imports.py          # ImportUtils  
├── extensions.py       # ExtensionFileLocator
├── errors.py          # ErrorMessageBuilder
├── http.py            # HeaderUtils
└── common.py          # Other shared utilities
```

### Testing Strategy

```python
# tests/utils/test_diagnostics.py
def test_traceback_formatter():
    """Test traceback formatting consistency."""
    try:
        raise ValueError("Test error")
    except ValueError as e:
        formatted = TracebackFormatter.format_exception(e)
        assert "ValueError: Test error" in formatted
        assert "test_traceback_formatter" in formatted

# tests/utils/test_extensions.py  
def test_extension_file_locator():
    """Test extension config file discovery."""
    # Test with extension.yaml
    temp_dir = tmp_path / "test_ext"
    temp_dir.mkdir()
    (temp_dir / "extension.yaml").write_text("name: test")
    
    config_file = ExtensionFileLocator.find_config_file(temp_dir)
    assert config_file == temp_dir / "extension.yaml"
    
    # Test fallback to plugin.yaml
    (temp_dir / "extension.yaml").unlink()
    (temp_dir / "plugin.yaml").write_text("name: test")
    
    config_file = ExtensionFileLocator.find_config_file(temp_dir)
    assert config_file == temp_dir / "plugin.yaml"

# tests/utils/test_imports.py
def test_import_utils():
    """Test import string parsing and importing."""
    # Test parsing
    module, attr = ImportUtils.parse_import_string("os.path.join")
    assert module == "os.path"
    assert attr == "join"
    
    # Test importing
    join_func = ImportUtils.import_from_string("os.path.join")
    assert callable(join_func)
    
    # Test validation
    assert ImportUtils.validate_import_string("valid.import.string")
    assert not ImportUtils.validate_import_string("invalid")
```

### Automated Duplication Detection

```python
# scripts/detect_duplication.py
import ast
import hashlib
from pathlib import Path

class DuplicationDetector:
    def __init__(self, min_lines=3):
        self.min_lines = min_lines
        self.code_blocks = {}
    
    def hash_code_block(self, lines):
        """Create hash of code block for comparison."""
        normalized = "\n".join(line.strip() for line in lines)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def detect_in_file(self, file_path):
        """Detect duplicated code blocks in file."""
        with open(file_path) as f:
            lines = f.readlines()
        
        for i in range(len(lines) - self.min_lines):
            block = lines[i:i + self.min_lines]
            block_hash = self.hash_code_block(block)
            
            if block_hash in self.code_blocks:
                print(f"Duplication found:")
                print(f"  File 1: {self.code_blocks[block_hash]}")
                print(f"  File 2: {file_path}:{i+1}")
            else:
                self.code_blocks[block_hash] = f"{file_path}:{i+1}"

# Add to CI/CD pipeline
detector = DuplicationDetector()
for py_file in Path("serv").glob("**/*.py"):
    detector.detect_in_file(py_file)
```

### Long-term Prevention

1. **Code Review Guidelines**: Require checking for existing utilities before adding new code
2. **Utility-First Development**: Encourage creating utilities for common operations
3. **Automated Detection**: Add duplication detection to CI/CD pipeline
4. **Documentation**: Maintain catalog of available utilities and when to use them