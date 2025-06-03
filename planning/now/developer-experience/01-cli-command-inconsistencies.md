# Documentation and Terminology Consistency Issues

## Problem Description

The Serv framework has **documentation inconsistencies** and **mixed terminology** that create confusion for new users. While the CLI commands themselves work correctly, documentation references outdated command patterns and inconsistently uses "plugins" vs "extensions".

### Current Issues

**Outdated Documentation References**:
- Quick start guide shows `serv app init` (line 18) instead of `serv create app`  
- Error messages in code still reference old patterns (commands.py:533)
- Some documentation shows non-existent commands

**Terminology Confusion**:
- Framework uses "extensions" but some docs mention "plugins"
- CLI help and documentation are inconsistent
- Mixed terminology confuses the mental model

**Examples Found**:
```bash
# Documentation shows (OUTDATED):
serv app init my-app

# Should be (CURRENT):
serv create app

# CLI error messages still reference old patterns
```

### User Impact

**New User Experience**:
1. User reads quick start guide with outdated commands
2. Follows outdated examples, commands fail
3. User tries `serv --help`, discovers correct structure
4. User loses confidence in documentation quality
5. Terminology confusion persists throughout learning

## Impact Assessment

- **Severity**: 🟡 **MEDIUM** (Documentation quality issue)
- **User Pain**: **MODERATE** (Confusing but not blocking)
- **Effort to Fix**: 🟢 **LOW** (Documentation updates and code cleanup)
- **Affected Users**: All new developers learning the framework

## Solution: Focus on Documentation Consistency

### Primary Goal: Complete Documentation Audit and Standardization

**Standardize All Documentation**:
- Use only current CLI commands (`serv create *`, `serv extension *`, etc.)
- Consistently use "extensions" terminology (never "plugins")
- Update all examples and references
- Clean up legacy code references

### Current CLI Structure (WORKING CORRECTLY):
```bash
# App Management
serv create app                    # Initialize new project

# Extension Management  
serv create extension --name <name>  # Create extension
serv extension enable <name>         # Enable extension
serv extension disable <name>        # Disable extension
serv extension list                  # List extensions

# Component Creation
serv create route --name <name>      # Create route
serv create middleware --name <name> # Create middleware
serv create listener --name <name>   # Create listener

# Development
serv launch                         # Start server
serv --dev launch                   # Start with dev mode
serv test                          # Run tests
serv shell                         # Interactive shell

# Configuration
serv config show                   # Show configuration
serv config validate              # Validate configuration
```

## Action Checklist

### Phase 1: Complete Documentation Audit ✅
- [x] Identify all documentation files with CLI references
- [ ] Audit quick-start guide (docs/getting-started/quick-start.md)
- [ ] Audit first-app tutorial (docs/getting-started/first-app.md)
- [ ] Audit README.md
- [ ] Check all demo README files
- [ ] Scan for "plugin" terminology usage

### Phase 2: Standardize Documentation 📝
- [ ] Update quick-start guide CLI commands
- [ ] Fix first-app tutorial commands  
- [ ] Update README.md examples
- [ ] Standardize all demo READMEs
- [ ] Replace "plugin" with "extension" everywhere
- [ ] Update CLI reference documentation

### Phase 3: Clean Up Code References 🧹
- [ ] Fix error messages in serv/cli/commands.py:533
- [ ] Update any remaining code comments with old terminology
- [ ] Ensure all help text is consistent
- [ ] Add command suggestion system for common mistakes

### Phase 4: Improve Help System 💡
- [ ] Enhance `serv --help` with examples
- [ ] Add better subcommand help text
- [ ] Include common usage patterns
- [ ] Add troubleshooting section to help

## Files Requiring Updates

### Documentation Files:
```
docs/getting-started/quick-start.md   # PRIMARY: Contains serv app init
docs/getting-started/first-app.md     # Check for outdated commands
README.md                             # Update CLI examples
demos/*/README.md                     # Standardize all demo docs
docs/cli-reference.md                 # Ensure accuracy
```

### Code Files:
```
serv/cli/commands.py                  # Fix line 533 error message
serv/cli/parser.py                    # Enhance help text
```

## Expected Changes

### Documentation Updates

**Quick Start Guide (docs/getting-started/quick-start.md)**:
```diff
- serv app init my-first-app
+ serv create app
```

**Error Messages (serv/cli/commands.py:533)**:
```diff
- "Run 'serv app init' to create a configuration file."
+ "Run 'serv create app' to create a configuration file."
```

**README.md CLI Examples**:
```diff
- serv create app
+ # Already correct! ✅

- # Create your first extension  
- serv create extension --name users
+ # Already correct! ✅
```

### Terminology Standardization

**Replace throughout documentation**:
- "plugin" → "extension"
- "plugin directory" → "extension directory"  
- "plugin management" → "extension management"

## Testing Strategy

### Documentation Validation
```bash
# Test all documented commands actually work
uv run python -m serv create app --help
uv run python -m serv extension --help
uv run python -m serv config --help

# Validate examples from documentation
grep -r "serv " docs/ | grep -v "create\|extension\|config\|launch"
```

### Automated Checks
```python
def test_documentation_cli_accuracy():
    """Ensure all CLI commands in docs actually work."""
    # Extract commands from markdown files
    # Test each command for basic syntax validity
    pass

def test_terminology_consistency():
    """Ensure consistent use of 'extension' vs 'plugin'."""
    # Scan docs for "plugin" usage
    # Flag inconsistencies
    pass
```

## Success Metrics

### Immediate Goals
- **Zero outdated CLI commands** in documentation
- **Consistent terminology** across all docs
- **Working examples** in all tutorials
- **Clean error messages** with current commands

### Long-term Goals  
- **Improved first-time success rate** for new users
- **Reduced support requests** about CLI confusion
- **Better documentation quality** overall
- **Consistent mental model** for users

## Implementation Priority

1. **HIGH**: Fix quick-start guide CLI commands (most visible)
2. **HIGH**: Update error messages in code
3. **MEDIUM**: Standardize terminology across docs
4. **MEDIUM**: Update demo READMEs
5. **LOW**: Enhance help text and suggestions

This approach focuses on **quality and consistency** rather than backwards compatibility, ensuring new users have a smooth and coherent experience with Serv.