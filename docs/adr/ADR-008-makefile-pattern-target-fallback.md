# ADR-008: Makefile Pattern Target Fallback Chain

**Status:** Accepted
**Date:** 2026-02-25
**Deciders:** AI CLI Preparation Team
**Tags:** makefile, installation, pattern-targets, fallback

## Context

The project uses GNU Make as the primary user interface. Historically, tool installation targets were either:

1. **Explicit targets** (e.g., `install-python`, `install-node`) with hardcoded commands
2. **Pattern targets** (e.g., `install-%`) that expanded to `./scripts/install_$*.sh`

The pattern target approach only worked for the ~15 tools that had dedicated install scripts. Running `make install-jq` or `make install-semgrep` would fail because no `scripts/install_jq.sh` or `scripts/install_semgrep.sh` existed, even though these tools had full catalog entries with all metadata needed for generic installation.

This meant 75+ catalog-only tools could not be managed via Make, despite having complete installation metadata in `catalog/*.json`.

**Problem:** How do we make `make install-<tool>`, `make upgrade-<tool>`, `make uninstall-<tool>`, and `make reconcile-<tool>` work for all 89 cataloged tools, while preserving backward compatibility with existing dedicated scripts?

## Decision

All four pattern targets (`install-%`, `upgrade-%`, `uninstall-%`, `reconcile-%`) use a **three-step fallback chain**:

```makefile
install-%: scripts-perms
	@if [ -f "./scripts/install_$*.sh" ]; then \
		./scripts/install_$*.sh; \
	elif [ -f "./catalog/$*.json" ]; then \
		./scripts/install_tool.sh "$*" install; \
	else \
		echo "Error: No installer found for '$*'" >&2; exit 1; \
	fi
```

### Fallback steps

1. **Dedicated script** (`./scripts/install_$*.sh`): If a tool-specific script exists, use it. This preserves existing behavior for complex tools like python, node, docker, rust, etc.

2. **Catalog entry** (`./catalog/$*.json`): If no dedicated script exists but a catalog entry does, delegate to the generic installer `scripts/install_tool.sh`, which reads the catalog metadata and routes to the appropriate method-specific installer.

3. **Error with helpful message**: If neither exists, print an error. This catches typos and requests for unknown tools.

### Explicit targets take precedence

GNU Make resolves explicit targets before pattern targets. Important tools retain their explicit targets for clarity in `make help` output and to allow tool-specific Make-level options:

```makefile
install-python: scripts-perms   ## Install Python toolchain via uv
	./scripts/install_python.sh

install-node: scripts-perms     ## Install Node.js via nvm
	./scripts/install_node.sh

# Generic fallback for everything else
install-%: scripts-perms
	@if [ -f "./scripts/install_$*.sh" ]; then ...
```

## Rationale

### Why a fallback chain (not just catalog-only)?

- **Backward compatibility**: Existing dedicated scripts continue to work unchanged
- **Graceful migration**: Tools can be migrated from dedicated scripts to catalog-only entries at any pace
- **Complex tools need scripts**: Python, Node, Docker, and Rust installations involve multi-step logic (version managers, repository setup, GPG keys) that does not fit in a JSON catalog entry

### Why check dedicated script first?

- Dedicated scripts may implement tool-specific logic beyond what the generic installer supports
- When both a dedicated script and a catalog entry exist, the script is authoritative
- This matches user expectations: if someone writes `install_foo.sh`, they expect it to be used

### Why not use Make's `$(wildcard)` or `$(shell)` for detection?

These are evaluated at Makefile parse time, not at target execution time. The `if [ -f ... ]` check in the recipe ensures the detection happens when the target is actually invoked, reflecting the current filesystem state.

## Consequences

### Positive

- **Complete coverage**: All 89 cataloged tools now work with `make install-<tool>`, `make upgrade-<tool>`, `make uninstall-<tool>`, and `make reconcile-<tool>`
- **Backward compatible**: No changes needed to existing dedicated scripts or explicit targets
- **Discoverable**: `make help` shows both explicit targets (with descriptions) and the pattern target
- **Consistent error handling**: Unknown tools get a clear error message

### Negative

- **Implicit behavior**: Users may not realize the fallback chain exists; `make install-jq` working "magically" could be surprising
- **Debugging**: When something fails, users need to understand whether the dedicated script or the generic installer was invoked

### Neutral

- **Dual maintenance**: Some tools have both a dedicated script and a catalog entry (the script takes precedence for Make targets, the catalog entry is used by `install_tool.sh` and the audit system)

## Implementation Notes

### Affected targets in `Makefile.d/user.mk`

| Pattern | Action passed to script |
|---------|------------------------|
| `install-%` | `install` (or no argument for dedicated scripts) |
| `upgrade-%` | `update` |
| `uninstall-%` | `uninstall` |
| `reconcile-%` | `reconcile` |

**Note on upgrade/update naming:** The user-facing Make target is `upgrade-%`, but it passes `update` as the action parameter to the underlying scripts. This is for historical compatibility -- the installer scripts originally used `update` as the action name. The Makefile uses the more intuitive `upgrade` terminology for the user interface.

### Testing the fallback

```bash
# Tool with dedicated script (uses install_python.sh)
make install-python

# Tool with catalog entry only (uses install_tool.sh → github_release_binary.sh)
make install-fd

# Unknown tool (error)
make install-nonexistent
# Error: No installer found for 'nonexistent'
```

## References

- **[ADR-007](ADR-007-generic-tool-installation-architecture.md)** - Generic tool installation architecture
- **[Makefile.d/user.mk](../../Makefile.d/user.mk)** - Pattern target definitions
- **[scripts/install_tool.sh](../../scripts/install_tool.sh)** - Generic installer orchestrator

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-25 | Initial decision accepted |
