# Tool Installation Catalog

This directory contains installation metadata for all development tools managed by this project.

## Structure

Each tool has its own JSON file: `catalog/<tool>.json`

## Installation Methods

### `github_release_binary`
Download and install binary from GitHub releases.

**Required fields:**
- `binary_name`: Name of the binary executable
- `download_url_template`: URL template with `{version}`, `{os}`, `{arch}` placeholders

**Optional fields:**
- `github_repo`: GitHub repository (owner/name) for version lookup
- `version_url`: Direct URL to fetch latest version string
- `fallback_url_template`: Alternative download URL if primary fails
- `arch_map`: Architecture name mappings (e.g., `{"x86_64": "amd64"}`)

**Example:** `kubectl.json`, `fd.json`, `ripgrep.json`

### `hashicorp_zip`
Download and install HashiCorp products from releases.hashicorp.com.

**Required fields:**
- `product_name`: HashiCorp product name (terraform, vault, consul, etc.)
- `binary_name`: Name of the binary executable
- `github_repo`: GitHub repository for version lookup

**Optional fields:**
- `arch_map`: Architecture name mappings

**Example:** `terraform.json`

### `aws_installer`
Install AWS CLI using official installer.

**Required fields:**
- `installer_url`: URL to AWS CLI installer zip
- `binary_name`: Name of the binary (usually "aws")

**Example:** `aws.json`

### `uv_tool`
Install Python tools via `uv tool install`.

**Required fields:**
- `package_name`: PyPI package name

**Example:** `semgrep.json`, `ruff.json`, `black.json`

### `package_manager`
Install tools via system package managers (apt, brew, dnf, pacman).

**Required fields:**
- `binary_name`: Name of the binary executable
- `packages`: Object with package names per manager

**Optional fields:**
- `notes`: Installation notes (e.g., "comes with Python")

**Example:** `pipx.json`, `yarn.json`, `sponge.json`

## Adding a New Tool

1. Create `catalog/<tool>.json` with appropriate metadata
2. The tool will automatically be available via `make install-<tool>`, `make upgrade-<tool>`, `make uninstall-<tool>`, and `make reconcile-<tool>`
3. No need to create a custom install script!

Currently **89 tools** are cataloged.

## Environment Variables

- `INSTALL_STRATEGY`: Where to install tools (USER, GLOBAL, CURRENT, PROJECT)
  - `USER` (default): Install to ~/.local/bin
  - `GLOBAL`: Install to /usr/local/bin (requires sudo)
  - `CURRENT`: Keep tool where currently installed
  - `PROJECT`: Install to ./.local/bin

## Usage

```bash
# Install a tool
scripts/install_tool.sh kubectl

# With custom strategy
INSTALL_STRATEGY=GLOBAL scripts/install_tool.sh terraform

# Via guide.sh (interactive upgrade)
make upgrade
```

## Architecture

All 89 tools have catalog entries. The generic installer (`scripts/install_tool.sh`) reads a tool's catalog JSON and delegates to the appropriate method-specific installer under `scripts/installers/`. Tools with complex installation needs (python, node, docker, rust, etc.) use `install_method: "dedicated_script"` to route to their existing bespoke scripts.

See [ADR-007](../docs/adr/ADR-007-generic-tool-installation-architecture.md) for the full architectural decision record.
