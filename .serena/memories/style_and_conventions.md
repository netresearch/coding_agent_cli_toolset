# Code Style and Conventions

## Python Style

### General Guidelines
- **PEP 8 compliance**: Follow standard Python style guide
- **Line length**: 127 characters (configured in pyproject.toml, .flake8)
- **Indentation**: 4 spaces (enforced by EditorConfig)
- **Line endings**: LF (Unix-style, enforced by EditorConfig)
- **Encoding**: UTF-8 (enforced by EditorConfig)
- **Trailing whitespace**: Trimmed (enforced by EditorConfig)

### Naming Conventions
- **Functions/variables**: snake_case (e.g., `extract_version_number`, `installed_version`)
- **Classes**: PascalCase (e.g., `Tool`, `ToolInfo`, `InstallResult`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `TIMEOUT_SECONDS`, `MANUAL_LOCK`, `TOOLS`)
- **Private functions**: Leading underscore (e.g., `_debug_log`, `_validate_cache`)
- **Module-level private**: Double underscore for truly private (rare, prefer single)

### Type Hints
- **Required**: Use type hints for all public functions
- **Import style**: `from __future__ import annotations` at top of file
- **Modern syntax**: Use `list[str]` instead of `List[str]`, `dict[str, int]` instead of `Dict[str, int]`
- **Optional types**: Use `str | None` instead of `Optional[str]`
- **Type aliases**: Define complex types as aliases (e.g., `VersionCache = dict[str, str]`)

### Dataclasses
- **Immutability**: Use `@dataclass(frozen=True)` for value objects (Tool, ToolInfo)
- **Mutable only when needed**: Use regular `@dataclass` for results/state (InstallResult, AuditResult)
- **Field types**: Always specify types explicitly
- **Default values**: Use factory functions for mutable defaults (`field(default_factory=list)`)

### Docstrings
- **Minimal**: Not required for simple functions with clear names
- **Required for**: Public API functions, complex algorithms, non-obvious behavior
- **Style**: Google-style docstrings (brief description, Args, Returns, Raises)
- **Focus**: Inline comments preferred over verbose docstrings

### Error Handling
- **Specific exceptions**: Catch specific exceptions, not bare `except:`
- **Fail gracefully**: Log errors, return sentinel values (empty string, None)
- **Best-effort operations**: Use try/except around network, subprocess, file I/O
- **Debug logging**: Use `_debug_log()` for suppressed exceptions when AUDIT_DEBUG=1

### Imports
- **Order**: Standard library → third-party → local modules
- **Grouping**: Separate groups with blank line
- **Style**: Explicit imports preferred (`from x import y`) over wildcard imports
- **Avoid circular**: Keep module dependencies acyclic

## Shell Script Style

### General Guidelines
- **Shebang**: `#!/usr/bin/env bash` (portable)
- **Strict mode**: `set -euo pipefail` at top of every script
- **Shellcheck-compliant**: Follow shellcheck recommendations
- **POSIX-compatible**: Where possible, avoid bashisms for portability

### Naming Conventions
- **Functions**: snake_case with descriptive names (e.g., `detect_os`, `install_with_apt`)
- **Variables**: UPPER_CASE for constants/globals, snake_case for locals
- **Private functions**: Leading underscore (e.g., `_internal_helper`)

### Error Handling
- **Exit codes**: Use appropriate exit codes (0=success, 1=general error, 2=usage error)
- **Logging**: Use echo for info, echo >&2 for errors
- **Cleanup**: Use trap for cleanup on exit/error

### Script Structure
```bash
#!/usr/bin/env bash
set -euo pipefail

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source shared utilities
source "${SCRIPT_DIR}/lib/common.sh"

# Main function
main() {
    # Implementation
}

# Run main if executed (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

## Makefile Style

### General Guidelines
- **Phony targets**: Declare all non-file targets as .PHONY
- **Variables**: Use ?= for defaults, := for immediate expansion
- **Help system**: Use ## comments for target documentation
- **Modularity**: Include Makefile.d/*.mk for logical grouping

### Target Naming
- **User targets**: Short, descriptive (audit, update, upgrade)
- **Dev targets**: Prefixed or namespaced (test-unit, lint-code)
- **Maintenance**: Prefixed (clean-build, publish-prod)

## Git Commit Style

### Commit Messages
- **Format**: Conventional Commits - `type(scope): description`
- **Types**: feat, fix, docs, chore, test, refactor, perf, style
- **Scope**: Optional but recommended (audit, cache, scripts, docs)
- **Description**: Imperative mood, lowercase, no period at end
- **Body**: Optional, wrap at 72 characters
- **Footer**: Reference issues/tickets if applicable

### Examples
```
feat(audit): add snapshot-based collect/render modes
fix(locks): enforce MANUAL_LOCK→HINTS_LOCK ordering
docs(prd): add Phase 2 specifications and ADRs
chore(cache): update latest_versions.json with atom_filtered hints
test(smoke): add validation for JSON output format
```

## Formatting Tools

### Python
- **Linter**: flake8 (configured in .flake8)
  - Max line length: 127
  - Ignore: E203 (whitespace before ':'), W503 (line break before binary operator)
  - Per-file ignores: __init__.py (F401), tests/* (F401, F811)
- **Type checker**: mypy (configured in pyproject.toml)
  - Python version: 3.9
  - Strict equality, warn on unused configs
- **Formatter**: black (configured in pyproject.toml, optional)
  - Line length: 127
  - Target versions: py39, py310, py311, py312
- **Import sorter**: isort (configured in pyproject.toml, optional)
  - Profile: black
  - Line length: 127

### Commands
```bash
make lint              # Run flake8
make lint-types        # Run mypy (when configured)
make format            # Run black + isort (optional)
make format-check      # Check formatting without changes
```

## Design Principles

### SOLID Principles
- **Single Responsibility**: Each function/module has one clear purpose
- **Open/Closed**: Extend via new Tool definitions, not modifying core logic
- **Liskov Substitution**: Subclasses/implementations must be substitutable
- **Interface Segregation**: Small, focused interfaces over monolithic ones
- **Dependency Inversion**: Depend on abstractions (e.g., package manager interface)

### Other Principles
- **DRY**: Don't Repeat Yourself - extract common patterns
- **KISS**: Keep It Simple - prefer simple solutions over complex ones
- **YAGNI**: You Aren't Gonna Need It - don't add speculative features
- **Law of Demeter**: Minimize coupling, talk to neighbors not strangers
- **Composition over Inheritance**: Favor composition for code reuse

### Specific Patterns
- **Frozen dataclasses**: Immutable value objects prevent accidental mutation
- **Lock ordering**: MANUAL_LOCK → HINTS_LOCK prevents deadlock
- **Parallel execution**: ThreadPoolExecutor for I/O-bound operations
- **Graceful degradation**: Best-effort operations with fallbacks
- **Atomic file writes**: Write to temp, then rename for consistency