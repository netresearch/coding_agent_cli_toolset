# Task Completion Checklist

## Pre-Commit Checklist

When completing any task that modifies code, follow these steps before committing:

### 1. Linting
```bash
make lint                # Run flake8
```
**Requirements:**
- No flake8 errors
- No new warnings introduced
- Respect max line length (127 characters)

### 2. Type Checking (Optional but Recommended)
```bash
make lint-types          # Run mypy (if configured)
```
**Requirements:**
- No type errors
- Type hints added for new public functions

### 3. Testing
```bash
./scripts/test_smoke.sh  # Run smoke tests
```
**Requirements:**
- Smoke tests pass
- Test affected functionality manually
- For specific tool changes: `CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only <tool>`

### 4. Audit Verification
```bash
make audit               # Verify snapshot renders correctly
make audit-<tool>        # Test specific tool if relevant
```
**Requirements:**
- Audit runs without errors
- Output format unchanged (unless intentional)
- No regression in tool detection

### 5. Documentation Updates
**Check if any of these need updating:**
- [ ] README.md - If user-facing behavior changed
- [ ] AGENTS.md - If agent workflow changed
- [ ] docs/ files - If architecture/API changed
- [ ] scripts/README.md - If installation scripts changed
- [ ] Inline comments - For complex logic

**Required documentation for specific changes:**
- New tool: Add to README.md tool categories
- New feature: Update docs/ARCHITECTURE.md and docs/API_REFERENCE.md
- Breaking change: Update CHANGELOG and docs/BREAKING_CHANGES.md (if exists)
- Script changes: Update scripts/README.md and script header comments

### 6. Git Commit
```bash
# Stage changes
git add <files>

# Review staged changes
git diff --staged

# Commit with conventional commit format
git commit -m "type(scope): description"
```

**Commit message requirements:**
- Format: `type(scope): description`
- Types: feat, fix, docs, chore, test, refactor, perf, style
- Scope: audit, cache, scripts, docs, etc. (optional but recommended)
- Description: Imperative mood, lowercase, no period
- Body: Optional, wrap at 72 characters
- Footer: Reference issues/tickets if applicable

**Examples:**
```bash
git commit -m "feat(audit): add support for tool-specific search paths"
git commit -m "fix(cache): prevent race condition in manual cache updates"
git commit -m "docs(readme): clarify offline mode behavior"
git commit -m "chore(deps): update packaging to 24.0"
```

## Task-Specific Checklists

### Adding a New Tool

- [ ] Add Tool definition to TOOLS tuple in cli_audit.py
- [ ] Choose correct source_kind (gh, pypi, crates, npm, gnu, skip)
- [ ] Provide source_args (owner/repo for gh, package name for others)
- [ ] Assign category (search, security, formatter, runtime, etc.)
- [ ] Add homepage URL if available
- [ ] Test detection: `CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only <tool>`
- [ ] Update README.md tool categories section
- [ ] Run `make update` to populate cache
- [ ] Run `make audit` to verify display
- [ ] Consider adding installation script (scripts/install_<tool>.sh)

### Modifying Cache Logic

- [ ] Understand lock ordering (MANUAL_LOCK → HINTS_LOCK)
- [ ] Test with concurrent operations (MAX_WORKERS=16)
- [ ] Verify atomic file writes (write to temp, rename)
- [ ] Test offline mode: `CLI_AUDIT_OFFLINE=1 make audit`
- [ ] Test online mode: `make update`
- [ ] Validate cache contents: `jq . latest_versions.json`
- [ ] Check for race conditions with parallel execution

### Changing Output Format

- [ ] Update smoke tests (scripts/test_smoke.sh)
- [ ] Test with smart_column.py: `make audit`
- [ ] Test JSON mode: `CLI_AUDIT_JSON=1 python3 cli_audit.py`
- [ ] Test with pipes: `python3 cli_audit.py | column -s '|' -t`
- [ ] Verify ANSI codes don't break formatting
- [ ] Test emoji/icon rendering (CLI_AUDIT_EMOJI=0/1)
- [ ] Document new format in README.md and docs/

### Adding Installation Script

- [ ] Follow template in scripts/install_tool.sh
- [ ] Use `set -euo pipefail` at top
- [ ] Add help text and usage examples
- [ ] Support install/update/uninstall/reconcile actions
- [ ] Make script executable: `chmod +x scripts/install_<tool>.sh`
- [ ] Add Make target to Makefile.d/user.mk
- [ ] Document in scripts/README.md
- [ ] Test on clean system (or VM)
- [ ] Ensure idempotency (safe to run multiple times)
- [ ] Add to scripts/AGENTS.md if agent-specific guidance needed

### Fixing a Bug

- [ ] Identify root cause (don't just fix symptoms)
- [ ] Write failing test first (TDD approach, when test suite exists)
- [ ] Implement fix
- [ ] Verify fix resolves issue
- [ ] Check for similar bugs elsewhere
- [ ] Update docs if behavior clarified
- [ ] Add regression test (when test suite exists)
- [ ] Consider if fix needs backport to stable branch

## Post-Commit Tasks

### After Pushing to Branch

- [ ] Monitor CI status (when CI added)
- [ ] Address any CI failures
- [ ] Update PR description with changes
- [ ] Link to relevant issues/tickets
- [ ] Request review from appropriate reviewers
- [ ] Address review feedback promptly

### After Merge to Main

- [ ] Delete feature branch: `git branch -d feature/name`
- [ ] Pull latest main: `git checkout main && git pull`
- [ ] Update local caches: `make update`
- [ ] Verify main branch: `make audit && make lint`
- [ ] Consider if release needed (maintainers)

## Release Checklist (Maintainers Only)

### Pre-Release

- [ ] Update version in pyproject.toml
- [ ] Update CHANGELOG.md with release notes
- [ ] Run full test suite: `make test` (when added)
- [ ] Run all linters: `make lint lint-types lint-security`
- [ ] Build distributions: `make build`
- [ ] Check distributions: `make check-dist`
- [ ] Test installation from built wheel locally

### Release

- [ ] Tag release: `git tag -a v2.0.0 -m "Release v2.0.0"`
- [ ] Push tag: `git push origin v2.0.0`
- [ ] Publish to TestPyPI: `make publish-test`
- [ ] Test install from TestPyPI
- [ ] Publish to PyPI: `make publish-prod`
- [ ] Create GitHub release with notes
- [ ] Announce release (if applicable)

### Post-Release

- [ ] Monitor for issues
- [ ] Update documentation site (if exists)
- [ ] Update examples/demos with new version
- [ ] Prepare hotfix branch for critical bugs

## Emergency Rollback

If a release has critical issues:

```bash
# 1. Pull back release from PyPI (if possible, contact PyPI support)

# 2. Create hotfix branch from previous tag
git checkout -b hotfix/v2.0.1 v2.0.0

# 3. Fix critical issue

# 4. Release hotfix following release checklist

# 5. Update main branch with fix
git checkout main
git merge hotfix/v2.0.1
git push

# 6. Delete hotfix branch after merge
git branch -d hotfix/v2.0.1
```

## Notes

### Manual Testing Scenarios

When automated tests are insufficient, test these scenarios manually:

**Version Detection:**
- [ ] Tool not installed
- [ ] Tool installed via different package managers
- [ ] Tool with non-standard version flag
- [ ] Multiple versions of same tool

**Network Scenarios:**
- [ ] No internet connection (offline mode)
- [ ] Slow internet (adjust timeout)
- [ ] GitHub rate limit hit
- [ ] PyPI/crates/npm temporarily unavailable

**Cache Scenarios:**
- [ ] Empty cache (first run)
- [ ] Stale cache (old versions)
- [ ] Corrupted cache (invalid JSON)
- [ ] Manual cache edits

**Parallel Execution:**
- [ ] MAX_WORKERS=1 (sequential)
- [ ] MAX_WORKERS=4 (moderate)
- [ ] MAX_WORKERS=16 (high, default)
- [ ] No race conditions or deadlocks

### Performance Benchmarks

Keep these performance targets in mind:

- **make update**: 3-10 seconds for 50+ tools
- **make audit**: <100ms (snapshot render)
- **make audit-offline**: <200ms (with hints)
- **Single tool audit**: <50ms

If changes degrade performance, investigate and optimize.