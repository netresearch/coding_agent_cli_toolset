# ADR-007: Generic Tool Installation Architecture

**Status:** Accepted
**Date:** 2026-02-25
**Deciders:** AI CLI Preparation Team
**Tags:** installation, catalog, generic-installer, architecture

## Context

The project originally required a dedicated shell script (`scripts/install_<tool>.sh`) for each tool it managed. As the catalog grew to 89+ tools, this approach did not scale:

- Each new tool required writing a bespoke install script, even for tools that follow identical installation patterns (e.g., downloading a GitHub release binary, or `uv tool install <package>`).
- Only ~15 tools had dedicated scripts. The remaining 75+ catalog-only tools could not be installed, upgraded, or uninstalled via Make targets.
- Duplicated logic across scripts (downloading, extracting, verifying, installing to PATH) was difficult to maintain.

**Problem:** How do we support install/upgrade/uninstall for all 89+ cataloged tools without writing and maintaining a dedicated script for each one?

## Decision

Implement a **three-tier generic installation architecture**:

### Tier 1: Catalog JSON entries

Each tool is described by a `catalog/<tool>.json` file containing metadata and installation parameters:

```json
{
  "name": "shfmt",
  "install_method": "github_release_binary",
  "binary_name": "shfmt",
  "github_repo": "mvdan/sh",
  "download_url_template": "https://github.com/mvdan/sh/releases/download/{version}/shfmt_{version}_linux_{arch}",
  "arch_map": {
    "x86_64": "amd64",
    "aarch64": "arm64",
    "armv7l": "arm"
  }
}
```

The `install_method` field determines which generic installer handles the tool.

### Tier 2: Method-specific installers

Generic installer scripts under `scripts/installers/` implement each installation method:

| Installer | Method | Example tools |
|-----------|--------|---------------|
| `github_release_binary.sh` | Download binary from GitHub releases | fd, ripgrep, bat, delta |
| `hashicorp_zip.sh` | Download from releases.hashicorp.com | terraform |
| `aws_installer.sh` | AWS official installer | aws |
| `uv_tool.sh` | `uv tool install` for Python packages | semgrep, ruff, black |
| `npm_global.sh` | `npm install -g` | eslint, prettier |
| `package_manager.sh` | System package managers (apt/brew/dnf) | sponge, pipx |
| `docker_plugin.sh` | Docker plugins | compose |
| `github_clone.sh` | Clone and build from source | rbenv, ruby-build |
| `npm_self_update.sh` | NPM self-update | npm |
| `dedicated_script.sh` | Delegate to a tool-specific script | python, node, docker |
| *(planned)* `go_install.sh` | Install via `go install` | templ |

**Note on `auto` install method:** 11 tools (including fd, ripgrep, bat, and hyperfine) use `"install_method": "auto"` instead of specifying a fixed installer. The `auto` method uses the reconciliation system (`scripts/lib/reconcile.sh`) to detect existing installations and choose the best available method from the tool's `available_methods` list in the catalog. This allows the system to adapt to the user's environment (e.g., preferring a GitHub binary release over cargo over apt, depending on what is already installed and available).

### Tier 3: Orchestrator

`scripts/install_tool.sh` is the central orchestrator that:

1. Reads `catalog/<tool>.json` to determine the install method
2. Validates the catalog entry has required fields
3. Delegates to the appropriate method-specific installer in `scripts/installers/`
4. Handles universal concerns (uninstall detection, status reporting)

For tools with `install_method: "auto"`, the orchestrator uses the reconciliation system (`scripts/lib/reconcile.sh`) to detect existing installations and choose the best approach.

## Rationale

### Why a catalog-driven approach?

- **Declarative over imperative**: Tool metadata is data, not code. Adding a tool is a JSON file, not a shell script.
- **Consistent behavior**: All tools using the same method share the same installer logic (download, extract, verify, install).
- **Testable**: Catalog entries can be validated programmatically. Installers can be tested independently of individual tools.

### Why keep dedicated scripts?

Some tools have genuinely complex installation requirements that cannot be captured in a simple JSON entry:

- **Python** (`install_python.sh`): Manages uv installation, Python version selection, virtual environments
- **Node** (`install_node.sh`): Manages nvm, node version selection, corepack
- **Docker** (`install_docker.sh`): Repository setup, GPG keys, daemon configuration
- **Rust** (`install_rust.sh`): Rustup installer, toolchain management

These tools use `install_method: "dedicated_script"` in their catalog entry, which routes to the existing script.

## Consequences

### Positive

- **Scalability**: Adding a new tool only requires creating a `catalog/<tool>.json` file
- **Consistency**: All tools of the same method type behave identically
- **Reduced maintenance**: Bug fixes in a method installer benefit all tools using that method
- **Complete coverage**: All 89 cataloged tools now support install, upgrade, uninstall, and reconcile operations

### Negative

- **Abstraction cost**: Some tools may need special handling that does not fit neatly into a generic installer
- **jq dependency**: The orchestrator requires `jq` to parse catalog JSON files

### Neutral

- **Coexistence**: Both dedicated scripts and generic installers coexist; the Makefile pattern targets handle the fallback transparently
- **Migration path**: Tools can start with a dedicated script and migrate to catalog-only as patterns stabilize, or vice versa

## Implementation Notes

### Directory structure

```
catalog/
  fd.json
  ripgrep.json
  semgrep.json
  ...               # 89 tool definitions
scripts/
  install_tool.sh   # Orchestrator
  install_python.sh # Dedicated script (complex tools)
  install_node.sh
  ...
  installers/
    github_release_binary.sh
    hashicorp_zip.sh
    uv_tool.sh
    ...             # 10 method-specific installers
```

### Adding a new tool

1. Create `catalog/<tool>.json` with `name`, `install_method`, and method-specific fields
2. Optionally add `tags` for group installation (`make install-core`, etc.)
3. The tool is immediately available via `make install-<tool>`, `make upgrade-<tool>`, etc.

## References

- **[ADR-008](ADR-008-makefile-pattern-target-fallback.md)** - Makefile pattern target fallback chain
- **[ADR-001](ADR-001-context-aware-installation.md)** - Context-aware installation modes
- **[ADR-002](ADR-002-package-manager-hierarchy.md)** - Package manager preference hierarchy
- **[catalog/README.md](../../catalog/README.md)** - Catalog documentation

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-25 | Initial decision accepted |
