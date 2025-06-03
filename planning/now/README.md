# Immediate Planning (Now)

This directory contains issues that need to be addressed in the next 1-2 releases to maintain framework stability, security, and usability.

## Categories

### Security (🔴 CRITICAL)
- **01-information-disclosure.md** - Fix debug information leaks
- **02-xss-vulnerabilities.md** - Address XSS vulnerabilities in error pages  
- **04-missing-authentication.md** - Add basic authentication middleware
- **09-missing-security-headers.md** - Implement security headers

### Architecture (🟡 HIGH)
- **01-route-class-complexity.md** - Simplify route handler system
- **02-circular-dependencies.md** - Resolve circular import issues

### Developer Experience (🟡 HIGH)  
- **01-cli-command-inconsistencies.md** - Standardize CLI interface
- **02-getting-started-experience.md** - Improve onboarding flow

### Code Quality (🟢 MEDIUM)
- **01-logic-errors.md** - Fix identified logic bugs
- **02-code-duplication.md** - Reduce code duplication

### Organization (🟢 MEDIUM)
- **01-extensions-vs-plugins-terminology.md** - Standardize terminology
- **02-public-api-boundaries.md** - Define clear API boundaries

## Implementation Strategy

Address items in priority order:
1. Security issues first (critical vulnerabilities)
2. Architecture fixes that enable other improvements  
3. Developer experience improvements for adoption
4. Code quality and organization polish

Each category should be tackled systematically before moving to the next.