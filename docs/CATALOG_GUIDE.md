# Catalog Guide: JSON Tool Definitions

**Last Updated:** 2025-11-03
**Version:** 2.0.0

## Overview

The catalog system allows tool definitions to be managed as JSON files instead of hardcoded Python, enabling:
- **Extensibility**: Add tools without code changes
- **Community Contributions**: Edit JSON vs Python code
- **Runtime Updates**: Tool definitions loaded dynamically
- **Clear Separation**: Data (JSON) vs Logic (Python)

**Location**: `catalog/` directory at project root
**Current Size**: 73 JSON tool definitions

## Quick Start

### View Existing Catalogs

```bash
# List all catalog entries
ls catalog/*.json

# View a specific entry
cat catalog/ripgrep.json

# Count catalog entries
ls catalog/*.json | wc -l
```

### Using ToolCatalog API

```python
from cli_audit.catalog import ToolCatalog, ToolCatalogEntry

# Load all catalog entries
catalog = ToolCatalog()

# Get specific tool
entry = catalog.get("ripgrep")
print(f"{entry.name}: {entry.description}")
print(f"Install method: {entry.install_method}")
print(f"GitHub: {entry.github_repo}")

# Check if tool exists
if catalog.has("fzf"):
    fzf = catalog.get("fzf")

# Get pinned version
ctags = catalog.get("ctags")
if ctags.pinned_version:
    print(f"ctags pinned to {ctags.pinned_version}")

# Iterate all entries
for name, entry in catalog.items():
    print(f"{name}: {entry.homepage}")
```

## JSON Schema

### Complete Field Reference

```json
{
  "name": "string (required)",
  "install_method": "string (required)",
  "description": "string (optional)",
  "homepage": "string (optional)",
  "github_repo": "string (optional, owner/repo format)",
  "binary_name": "string (optional)",
  "version_flag": "string (optional, default: --version)",
  "download_url_template": "string (optional)",
  "arch_map": {
    "x86_64": "string",
    "aarch64": "string",
    "armv7l": "string"
  },
  "available_methods": [
    {
      "method": "string",
      "priority": "number",
      "config": {}
    }
  ],
  "requires": ["string (dependency names)"],
  "tags": ["string (categorization)"],
  "pinned_version": "string (optional, pins to specific version)",
  "notes": "string (optional, additional context)"
}
```

### Field Descriptions

#### Required Fields

**`name`** (string)
- Tool display name
- Should match common usage (e.g., "ripgrep" not "rg")
- Used for lookups and display

**`install_method`** (string)
- Primary installation method
- Valid values:
  - `"github_release_binary"` - Download from GitHub Releases
  - `"cargo"` - Install via Rust cargo
  - `"npm"` - Install via npm/node
  - `"pypi"` - Install via pip/PyPI
  - `"apt"` - Install via apt package manager
  - `"brew"` - Install via Homebrew
  - `"auto"` - Automatic method selection (requires `available_methods`)
  - `"manual"` - Manual installation only

#### Optional Fields

**`description`** (string)
- Brief tool description
- Used in audit output and documentation

**`homepage`** (string)
- Tool homepage or documentation URL
- Displayed in audit output with OSC8 links

**`github_repo`** (string)
- GitHub repository in `owner/repo` format
- Used for GitHub Release version lookups
- Required for `github_release_binary` method

**`binary_name`** (string)
- Executable name to search on PATH
- Defaults to `name` if not specified
- Can differ from display name (e.g., `"rg"` for ripgrep)

**`version_flag`** (string)
- Flag to extract version information
- Common values: `"--version"`, `"-v"`, `"version"`
- Defaults to `"--version"`

**`download_url_template`** (string)
- URL template for binary downloads
- Supports placeholders:
  - `{version}` - Full version tag (e.g., "v1.2.3")
  - `{version_nov}` - Version without 'v' prefix (e.g., "1.2.3")
  - `{arch}` - Architecture from arch_map

**`arch_map`** (object)
- Maps system architecture to download architecture
- Keys: System arch (`x86_64`, `aarch64`, `armv7l`)
- Values: Download arch (varies by tool)

**`available_methods`** (array)
- Multiple installation methods with priorities
- Used when `install_method` is `"auto"`
- Each method has:
  - `method`: Installation method name
  - `priority`: Lower = higher priority (1 = first choice)
  - `config`: Method-specific configuration

**`requires`** (array of strings)
- List of dependency tool names
- Used for installation ordering
- Example: `["python", "pip"]`

**`tags`** (array of strings)
- Categorization tags
- Common tags: `"core"`, `"optional"`, `"dev"`
- Used for filtering and organization

**`pinned_version`** (string)
- Pin tool to specific version
- Prevents upgrade suggestions
- Example: `"1.2.3"` or `"v1.2.3"`

**`notes`** (string)
- Additional context or caveats
- Displayed in audit output
- Examples: architecture limitations, special requirements

## Examples

### Example 1: Simple GitHub Binary

```json
{
  "name": "ast-grep",
  "install_method": "github_release_binary",
  "description": "A CLI tool for code structural search, lint and rewriting",
  "homepage": "https://github.com/ast-grep/ast-grep",
  "github_repo": "ast-grep/ast-grep",
  "binary_name": "ast-grep",
  "download_url_template": "https://github.com/ast-grep/ast-grep/releases/download/{version}/app-{arch}-unknown-linux-gnu.zip",
  "arch_map": {
    "x86_64": "x86_64",
    "aarch64": "aarch64",
    "armv7l": "armv7"
  }
}
```

### Example 2: Complex with Multiple Methods

```json
{
  "name": "bat",
  "install_method": "auto",
  "description": "A cat clone with syntax highlighting and Git integration",
  "homepage": "https://github.com/sharkdp/bat",
  "github_repo": "sharkdp/bat",
  "binary_name": "bat",
  "download_url_template": "https://github.com/sharkdp/bat/releases/download/{version}/bat-{version}-{arch}-unknown-linux-musl.tar.gz",
  "arch_map": {
    "x86_64": "x86_64",
    "aarch64": "aarch64",
    "armv7l": "armv7"
  },
  "available_methods": [
    {
      "method": "github_release_binary",
      "priority": 1,
      "config": {
        "repo": "sharkdp/bat",
        "asset_pattern": "bat-.*-x86_64-unknown-linux-musl.tar.gz"
      }
    },
    {
      "method": "cargo",
      "priority": 2,
      "config": {
        "crate": "bat"
      }
    },
    {
      "method": "apt",
      "priority": 3,
      "config": {
        "package": "bat"
      }
    }
  ],
  "requires": [],
  "tags": ["core"]
}
```

### Example 3: Pinned Version

```json
{
  "name": "ctags",
  "install_method": "github_release_binary",
  "description": "Universal Ctags - generates tag files for code navigation",
  "homepage": "https://github.com/universal-ctags/ctags",
  "github_repo": "universal-ctags/ctags",
  "binary_name": "ctags",
  "pinned_version": "5.9.0",
  "notes": "Pinned to 5.9.0 for compatibility"
}
```

### Example 4: Package Manager Installation

```json
{
  "name": "black",
  "install_method": "pypi",
  "description": "The uncompromising Python code formatter",
  "homepage": "https://github.com/psf/black",
  "github_repo": "psf/black",
  "binary_name": "black",
  "requires": ["python", "pip"],
  "tags": ["python", "formatter"]
}
```

## Creating New Catalog Entries

### Step 1: Create JSON File

```bash
# Create new file in catalog/
nano catalog/my-tool.json
```

### Step 2: Define Tool

```json
{
  "name": "my-tool",
  "install_method": "github_release_binary",
  "description": "My amazing development tool",
  "homepage": "https://github.com/owner/my-tool",
  "github_repo": "owner/my-tool",
  "binary_name": "my-tool",
  "version_flag": "--version",
  "download_url_template": "https://github.com/owner/my-tool/releases/download/{version}/my-tool-{arch}-linux.tar.gz",
  "arch_map": {
    "x86_64": "x86_64",
    "aarch64": "arm64"
  },
  "tags": ["utility"]
}
```

### Step 3: Validate JSON

```bash
# Validate syntax
jq . catalog/my-tool.json

# Should output formatted JSON without errors
```

### Step 4: Test Detection

```bash
# Install your tool manually first
# Then test detection:
python3 audit.py --only my-tool

# Or use ToolCatalog API:
python3 -c "
from cli_audit.catalog import ToolCatalog
catalog = ToolCatalog()
entry = catalog.get('my-tool')
print(f'Loaded: {entry.name}')
"
```

### Step 5: Update Snapshot

```bash
# Collect fresh data including new tool
make update

# Verify in audit
make audit | grep my-tool
```

## Best Practices

### Naming Conventions

**Tool Name:**
- Use common/official name (e.g., "ripgrep" not "rg")
- Lowercase, hyphenated for multi-word names
- Match PyPI/crates/npm package name when applicable

**Binary Name:**
- Specify actual executable name
- May differ from display name (e.g., `"rg"` for ripgrep)
- Check PATH: `which tool-name`

**GitHub Repo:**
- Always format as `"owner/repo"`
- Match GitHub URL: `github.com/owner/repo`
- Case-sensitive

### URL Templates

**Version Placeholders:**
- `{version}`: Full tag (e.g., "v1.2.3") - most common
- `{version_nov}`: No 'v' prefix (e.g., "1.2.3") - some tools

**Architecture Placeholders:**
- `{arch}`: Mapped via `arch_map`
- Define all supported architectures in `arch_map`

**Example Patterns:**
```
https://github.com/owner/repo/releases/download/{version}/tool-{version}-{arch}-linux.tar.gz
https://github.com/owner/repo/releases/download/{version_nov}/tool-{arch}.zip
https://github.com/owner/repo/releases/download/v{version_nov}/tool-linux-{arch}
```

### Architecture Mapping

**Common Mappings:**
```json
"arch_map": {
  "x86_64": "x86_64",       // Most common
  "aarch64": "aarch64",     // ARM 64-bit
  "armv7l": "armv7"         // ARM 32-bit
}
```

**Tool-Specific Examples:**
```json
// Rust-style
"arch_map": {
  "x86_64": "x86_64-unknown-linux-musl",
  "aarch64": "aarch64-unknown-linux-musl"
}

// Go-style
"arch_map": {
  "x86_64": "amd64",
  "aarch64": "arm64",
  "armv7l": "armv6"
}
```

### Version Flags

**Test First:**
```bash
# Try common flags
tool --version   # Most common
tool -v          # Alternative
tool version     # Subcommand style
tool -V          # Capital variant
```

**Handle Special Cases:**
```json
{
  "version_flag": "--version",  // Most tools
  "version_flag": "version",    // Some CLIs (e.g., kubectl)
  "version_flag": "-v"          // Short form
}
```

### Pinning Versions

**When to Pin:**
- Breaking changes in new versions
- Compatibility requirements
- Stability for production use
- Testing specific version behavior

**How to Pin:**
```json
{
  "pinned_version": "1.2.3",   // Without 'v'
  "notes": "Pinned for compatibility with project X"
}
```

**Unpinning:**
```json
{
  "pinned_version": "",  // Empty string
  // OR remove field entirely
}
```

## Fallback to Python TOOLS

If a tool is not in the catalog, the system falls back to the Python `TOOLS` tuple in `cli_audit/tools.py`:

```python
# cli_audit/tools.py
TOOLS: tuple[Tool, ...] = (
    Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"), "search", "make install-core"),
    Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd"), "search", "make install-core"),
    # ... 70+ tools
)
```

**Priority:**
1. JSON catalog entry (if exists)
2. Python TOOLS tuple (fallback)
3. Manual-only (no definition)

## Advanced Features

### Multiple Installation Methods

```json
{
  "install_method": "auto",
  "available_methods": [
    {
      "method": "github_release_binary",
      "priority": 1,
      "config": {
        "repo": "owner/repo",
        "asset_pattern": "tool-.*-x86_64.tar.gz"
      }
    },
    {
      "method": "cargo",
      "priority": 2,
      "config": {
        "crate": "tool-name"
      }
    }
  ]
}
```

**Behavior:**
- System tries methods in priority order (1 = first)
- Falls back if primary method fails
- Stops at first successful installation

### Dependency Management

```json
{
  "name": "black",
  "requires": ["python", "pip"],
  "install_method": "pypi"
}
```

**Behavior:**
- Dependencies installed first
- Circular dependencies detected and prevented
- Topological sort for correct order

### Tagging and Categorization

```json
{
  "tags": ["core", "python", "formatter", "recommended"]
}
```

**Uses:**
- Filtering: Install only "core" tools
- Organization: Group by category
- Presets: Define role-based toolsets

## ToolCatalog API Reference

### Class: ToolCatalog

```python
from cli_audit.catalog import ToolCatalog

# Initialize
catalog = ToolCatalog()  # Loads from default catalog/ directory
catalog = ToolCatalog("path/to/catalog")  # Custom directory
```

### Methods

**`get(name: str) -> ToolCatalogEntry | None`**
```python
entry = catalog.get("ripgrep")
if entry:
    print(entry.description)
```

**`has(name: str) -> bool`**
```python
if catalog.has("fzf"):
    print("fzf catalog entry exists")
```

**`items() -> Iterator[tuple[str, ToolCatalogEntry]]`**
```python
for name, entry in catalog.items():
    print(f"{name}: {entry.homepage}")
```

**`keys() -> Iterator[str]`**
```python
for name in catalog.keys():
    print(name)
```

**`__len__() -> int`**
```python
print(f"Catalog has {len(catalog)} entries")
```

### Class: ToolCatalogEntry

```python
from cli_audit.catalog import ToolCatalogEntry

# Fields
entry.name: str
entry.description: str
entry.homepage: str
entry.github_repo: str
entry.binary_name: str
entry.install_method: str
entry.package_name: str
entry.script: str
entry.pinned_version: str
entry.notes: str
```

## Troubleshooting

### Catalog Not Loading

**Symptoms:** No tools detected, empty catalog

**Checks:**
```bash
# Verify directory exists
ls catalog/

# Check file count
ls catalog/*.json | wc -l

# Validate JSON syntax
for f in catalog/*.json; do
    jq . "$f" >/dev/null || echo "Invalid: $f"
done
```

**Solution:**
- Ensure `catalog/` directory exists at project root
- Fix JSON syntax errors
- Check file permissions

### Tool Not Detected

**Symptoms:** Tool in catalog but not showing in audit

**Checks:**
```python
# Test catalog loading
from cli_audit.catalog import ToolCatalog
catalog = ToolCatalog()
print(f"Loaded {len(catalog)} entries")

# Check specific tool
entry = catalog.get("my-tool")
print(f"Found: {entry is not None}")
```

**Solution:**
- Verify JSON file exists: `ls catalog/my-tool.json`
- Check JSON syntax: `jq . catalog/my-tool.json`
- Ensure `name` field matches filename

### Version Detection Fails

**Symptoms:** Tool shows as "installed" without version

**Checks:**
```bash
# Test version flag
my-tool --version
my-tool -v
my-tool version
```

**Solution:**
- Update `version_flag` in JSON
- Check tool's help: `my-tool --help`
- Some tools don't support version flags (use `"version_flag": ""`)

## Contributing Catalog Entries

### Contribution Workflow

1. **Fork Repository**
2. **Create JSON File**
   ```bash
   nano catalog/new-tool.json
   ```
3. **Validate**
   ```bash
   jq . catalog/new-tool.json
   python3 audit.py --only new-tool
   ```
4. **Test**
   ```bash
   make update
   make audit | grep new-tool
   ```
5. **Submit PR**
   - Include tool name in PR title
   - Describe tool purpose
   - Link to official homepage

### Contribution Guidelines

**Required:**
- Valid JSON syntax
- At minimum: `name`, `install_method`
- Clear, concise `description`
- Accurate `homepage` URL

**Recommended:**
- Complete installation details
- Architecture mappings
- Version flag specification
- Usage notes if non-standard

**Prohibited:**
- Malware or security risks
- Duplicate entries (check existing first)
- Proprietary/closed-source without clear license

## Migration from Python TOOLS

### Gradual Migration Strategy

**Phase 1: Coexistence**
- Keep Python TOOLS tuple
- Add JSON catalog entries
- Catalog takes precedence when present

**Phase 2: JSON Primary**
- Most tools defined in JSON
- Python TOOLS as fallback only
- Document migration in CHANGELOG

**Phase 3: JSON Only** (Future)
- Remove Python TOOLS tuple
- All tools in JSON catalog
- Breaking change (major version)

### Conversion Helper

```python
# Convert Python Tool to JSON
from cli_audit.tools import TOOLS
import json

for tool in TOOLS:
    catalog_entry = {
        "name": tool.name,
        "install_method": "github_release_binary",  # Adjust
        "github_repo": f"{tool.source_args[0]}/{tool.source_args[1]}",
        "binary_name": tool.candidates[0],
        "homepage": f"https://github.com/{tool.source_args[0]}/{tool.source_args[1]}",
        "description": "",  # Add manually
    }
    filename = f"catalog/{tool.name}.json"
    with open(filename, "w") as f:
        json.dump(catalog_entry, f, indent=2)
```

## Summary

**Catalog System Benefits:**
- ✅ Add tools without code changes
- ✅ Community-friendly JSON format
- ✅ Runtime extensibility
- ✅ Clear data/logic separation
- ✅ Version pinning support
- ✅ Multi-method installation

**Getting Started:**
1. Browse `catalog/` for examples
2. Copy similar tool's JSON
3. Modify for your tool
4. Validate and test
5. Submit PR

**Resources:**
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Transitioning to v2.0
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [API_REFERENCE.md](API_REFERENCE.md) - Python API
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Contributing code

---

**Questions?** Check existing catalog entries for patterns or open an issue!
