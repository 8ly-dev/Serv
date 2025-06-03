# Organization Issues

This directory contains project organization and structure problems that affect developer experience, maintainability, and code clarity.

## Critical Organization Issues (🔴 HIGH PRIORITY)

| Issue | Developer Impact | Effort |
|-------|-----------------|--------|
| [Extensions vs Plugins Terminology](./01-extensions-vs-plugins-terminology.md) | 🔴 High | 🟢 Low |
| [Public API Boundaries](./02-public-api-boundaries.md) | 🔴 High | 🟡 Medium |
| [CLI Organization](./03-cli-organization.md) | 🟡 Medium | 🟢 Low |

## Module Structure Issues (📁 MEDIUM PRIORITY)

| Issue | Maintainability | Effort |
|-------|----------------|--------|
| [Import Pattern Inconsistencies](./04-import-pattern-inconsistencies.md) | 🟡 Medium | 🟢 Low |
| [Configuration File Naming](./05-configuration-file-naming.md) | 🟡 Medium | 🟢 Low |
| [Demo Organization](./06-demo-organization.md) | 🟡 Medium | 🟡 Medium |

## Documentation & Examples (📚 LOW PRIORITY)

| Issue | User Experience | Effort |
|-------|----------------|--------|
| [Documentation Structure](./07-documentation-structure.md) | 🟡 Medium | 🟡 Medium |
| [Test Organization](./08-test-organization.md) | 🟢 Low | 🟢 Low |
| [Module Responsibility](./09-module-responsibility.md) | 🟡 Medium | 🟡 Medium |

## Implementation Strategy

1. **Week 1**: Fix terminology and public API issues
2. **Week 2**: Standardize import patterns and file naming
3. **Week 3**: Reorganize demos and documentation
4. **Week 4**: Clean up test organization and module boundaries

## Success Metrics

- **Terminology Consistency**: Zero mentions of "plugins" in user-facing content
- **API Clarity**: All common imports available from main package
- **Developer Onboarding**: < 2 minutes to understand project structure
- **Code Navigation**: Clear module boundaries and responsibilities