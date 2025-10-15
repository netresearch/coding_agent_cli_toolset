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

## Adding a New Tool

1. Create `catalog/<tool>.json` with appropriate metadata
2. The tool will automatically use the generic installer for its method
3. No need to create a custom install script!

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

## Migration Status

Tools with catalog entries use the new system. Tools without catalog entries fall back to legacy `install_core.sh`.

**Migrated:**
- kubectl
- terraform
- aws
- semgrep

**To migrate:** Add catalog entries for remaining tools from `install_core.sh`
