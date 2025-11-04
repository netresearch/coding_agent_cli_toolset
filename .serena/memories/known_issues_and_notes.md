# Known Issues and Notes

## Version Discrepancies

### glab (GitLab CLI)
**Issue**: Cached latest version may be outdated
**Details**: 
- User reported latest version is 1.74.0 (from https://gitlab.com/gitlab-org/cli/-/releases)
- Cache may have older version (1.22 mentioned)
- **Action needed**: Update cache entry for glab when running `make update`

**Resolution:**
```bash
# Manual update in latest_versions.json
# Or run update to fetch latest from GitHub releases
make update

# Verify
make audit-glab
```

## System-Specific Notes

### Operating System
- **Platform**: Linux
- **System**: WSL2 (Windows Subsystem for Linux)
- **Kernel**: 6.6.87.2-microsoft-standard-WSL2
- **Current Date**: 2025-10-23

### Python Environment
- **Version**: Python 3.10+ required (Python 3.14.0rc2 currently available)
- **Package Management**: uv preferred over pipx/pip
- **Virtual Environments**: Optional, not required for core audit

### Git Configuration
- **Current Branch**: main
- **Default Branch**: main (for PRs)
- **Commit Style**: Conventional Commits (type(scope): description)

## WSL2-Specific Considerations

### File System
- **Line Endings**: LF enforced (EditorConfig)
- **Git Config**: May need `git config --global core.autocrlf input`
- **Permissions**: chmod may behave differently than native Linux

### Network
- **WSL2 uses NAT**: May affect network detection
- **DNS**: Sometimes needs manual configuration
- **Proxy**: Check if corporate proxy affects GitHub/PyPI access

### Tool Availability
- **Some tools may need manual install**: Not all package managers work identically in WSL2
- **Docker**: May need Docker Desktop with WSL2 integration
- **Snap**: May not work in WSL2, prefer apt/brew alternatives

## Cache Management Notes

### Lock Ordering
**Critical**: Always acquire locks in this order to prevent deadlock:
1. MANUAL_LOCK (manual cache updates)
2. HINTS_LOCK (lookup hints updates)

**Never acquire in reverse order!**

### Atomic Writes
All cache updates use atomic file operations:
1. Write to temporary file
2. Rename to final location
3. Prevents corruption from interrupted writes

### Lookup Hints
`latest_versions.json` contains `__hints__` key with working upstream methods:
- Speeds up subsequent runs
- Safe to edit or remove (will rebuild)
- Format: `"tool_name": "gh"` or `"tool_name": "pypi"`, etc.

## Common Troubleshooting

### Version Detection Fails
**Symptoms**: Tool shows as NOT INSTALLED but is in PATH
**Causes**:
- Non-standard version flag
- Tool doesn't support --version or -v
- Version output parsing fails

**Solution**:
```bash
# Debug single tool
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only <tool>

# Check manually
which <tool>
<tool> --version
<tool> -v
<tool> version
```

### Network Timeouts
**Symptoms**: Empty upstream versions, slow updates
**Causes**:
- Slow network connection
- GitHub rate limiting
- Upstream service temporarily down

**Solutions**:
```bash
# Increase timeout
CLI_AUDIT_TIMEOUT_SECONDS=10 make update

# Use offline mode
make audit-offline

# Check rate limit
curl -I https://api.github.com/rate_limit

# Use GitHub token to increase rate limit
export GITHUB_TOKEN=ghp_...
make update
```

### Cache Corruption
**Symptoms**: Invalid JSON errors, wrong versions
**Solution**:
```bash
# Nuclear option: delete and regenerate
rm latest_versions.json tools_snapshot.json
make update
make audit
```

### Parallel Execution Issues
**Symptoms**: Deadlocks, race conditions, inconsistent results
**Solutions**:
```bash
# Reduce workers
CLI_AUDIT_MAX_WORKERS=4 make update

# Sequential execution for debugging
CLI_AUDIT_MAX_WORKERS=1 make update

# Check lock ordering in code changes
```

## Performance Notes

### Benchmark Targets
- **make update**: 3-10s for 50+ tools (parallel, MAX_WORKERS=16)
- **make audit**: <100ms (snapshot render)
- **make audit-offline**: <200ms (with hints)
- **Single tool**: <50ms

### Optimization Tips
- Use snapshot-based workflow (separate collect/render)
- Enable FAST_MODE for development: `CLI_AUDIT_FAST=1`
- Disable unnecessary features: `CLI_AUDIT_TIMINGS=0`, `CLI_AUDIT_PROGRESS=0`
- Increase MAX_WORKERS if more CPU cores: `CLI_AUDIT_MAX_WORKERS=32`

## Development Environment

### Recommended Tools for Development
- **pyflakes**: Linting (make lint)
- **mypy**: Type checking (optional, make lint-types)
- **black**: Formatting (optional, make format)
- **isort**: Import sorting (optional, make format)
- **shellcheck**: Shell script linting
- **jq**: JSON manipulation and validation

### Optional Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"

# Enable direnv (optional)
direnv allow
```

### Editor Configuration
- **EditorConfig**: .editorconfig present (4 spaces, LF, UTF-8, trim trailing)
- **VSCode**: Respect EditorConfig, install Python extension
- **Vim/Neovim**: Use editorconfig plugin
- **IntelliJ/PyCharm**: EditorConfig support built-in

## Future Work (Phase 2 Complete, Phase 3 Planned)

### Phase 2 Status (Complete)
- [x] Context-aware installation management
- [x] Breaking change detection
- [x] Installation reconciliation
- [x] Bulk operations
- [x] Configuration file support
- [x] Upgrade workflows

### Phase 3 (Planned)
- [ ] Advanced dependency resolution
- [ ] Rollback mechanisms
- [ ] Integration tests
- [ ] CI/CD pipeline
- [ ] Performance benchmarks
- [ ] Additional package managers

See [docs/PRD.md](docs/PRD.md) for comprehensive Phase 2 specifications.

## Contributing Notes

### PR Size Guidelines
- **Ideal**: ~≤300 net LOC changed
- **Rationale**: Easier to review, faster to merge, lower risk
- **Large changes**: Break into multiple PRs when possible

### Review Process
1. Self-review checklist (see task_completion_checklist.md)
2. CI checks pass (when added)
3. Documentation updated in same PR
4. No secrets or credentials committed
5. Conventional commit messages
6. Linked to issue/ticket if applicable

### Communication
- **Issues**: GitHub Issues for bugs, features, discussions
- **PRs**: Clear description, link to issue, changelog section
- **Commits**: Self-documenting with Conventional Commits format