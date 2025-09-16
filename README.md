# AI CLI Preparation

A minimal utility to verify that tools used by AI coding agents are installed and up to date on your system. It audits versions of common agent toolchain CLIs against the latest upstream releases and prints a pipe-delimited report suitable for quick human scan or downstream tooling.

## Scope: agent toolchain
- This audit targets CLIs that coding agents commonly utilize themselves if present on the machine. It is agent-focused; tools may be reported as NOT INSTALLED on your host if you don't use them.
- Upstream versions are resolved from GitHub releases, PyPI, crates.io, or the npm registry for Node CLIs.

## Primary Use Case: AI coding agent readiness

Use this tool to quickly confirm that the CLIs your AI coding agents rely on are present and current. If tools are missing or outdated, use the provided installer scripts (see Installation scripts) or your preferred package manager to remediate, then re-run the audit until everything is ready.

## Features
- Detects installed versions across PATH (and `~/.cargo/bin` for Rust tools)
- Fetches latest upstream versions from GitHub, PyPI, crates.io, and npm registry (for `npm`/`pnpm`/`yarn` and Node-only CLIs)
- Handles tools with non-standard version flags (e.g., `entr`, `sponge`)
- Short timeouts to avoid hanging
- Simple, parse-friendly output

## Output Format
The program prints a header followed by one line per tool (6 columns):

```
state|tool|installed|installed_method|latest_upstream|upstream_method
+|fd|9.0.0 (140ms)|apt/dpkg|9.0.0 (220ms)|github
...
```

- `state`: single-character/emoji indicator of status
- `tool`: logical tool name
- `installed`: local version display (may include timing)
- `installed_method`: detected installation source (e.g., `uv tool`, `npm (user)`, `apt/dpkg`)
- `latest_upstream`: upstream version display (may include timing)
- `upstream_method`: where the upstream version came from (`github`, `pypi`, `crates`, `npm`, `gnu-ftp`)

### JSON mode

Set `CLI_AUDIT_JSON=1` to emit a JSON array of tool objects instead of the table:

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'
```

Fields (subset):
- `tool`: logical tool name
- `installed`: formatted local version display (may include timings)
- `installed_version`: parsed semantic version of the local tool (when available)
- `latest_upstream`: formatted upstream version display (may include timings)
- `latest_version`: parsed semantic version of the upstream tool (when available)
- `installed_method`: detected installation source (e.g., "uv tool", "npm (user)")
- `installed_path_resolved`: realpath via which(1) (kept for backwards compatibility)
- `classification_reason`: reason derived from classifying the which(1) path
- `installed_path_selected`: path of the executable actually selected by the audit run
- `classification_reason_selected`: reason string for the selected path's classification
- `upstream_method`: source used for latest lookup (e.g., "github", "uv tool")
- `status`: `UP-TO-DATE`, `OUTDATED`, `NOT INSTALLED`, or `UNKNOWN`

Example (abridged):

```json
{
  "tool": "eslint",
  "installed": "9.35.0 (340ms)",
  "installed_version": "9.35.0",
  "installed_method": "npm (user)",
  "installed_path_resolved": "/home/you/.local/lib/node_modules/eslint/bin/eslint.js",
  "classification_reason": "path-under-~/.local/lib/node_modules",
  "installed_path_selected": "/home/you/.local/lib/node_modules/eslint/bin/eslint.js",
  "classification_reason_selected": "path-under-~/.local/lib/node_modules",
  "latest_upstream": "9.35.0 (800ms)",
  "latest_version": "9.35.0",
  "upstream_method": "github",
  "status": "UP-TO-DATE"
}
```

## Tool categories (agent-focused)
- Core runtimes & package managers: `python`, `pip`, `pipx`, `poetry`, `node`, `npm`, `pnpm`, `yarn`
- Search & code-aware tools: `ripgrep`, `ast-grep`, `fzf`, `fd`, `xsv`
- Editors/helpers and diffs: `ctags`, `delta`, `bat`, `just`
- JSON/YAML processors: `jq`, `yq`, `dasel`, `fx`
- HTTP/CLI clients: `httpie`, `curlie`
- Watch/run automation: `entr`, `watchexec`, `direnv`
- Security & compliance: `semgrep`, `bandit`, `gitleaks`, `trivy`
- Git helpers: `git-absorb`, `git-branchless`
- Formatters & linters: `black`, `isort`, `flake8`, `eslint`, `prettier`, `shfmt`, `shellcheck`
- VCS & platforms: `git`, `gh` (GitHub CLI), `glab` (GitLab CLI)
- Cloud & infra: `aws`, `kubectl`, `terraform`, `docker`, `dive`

Note: Not all of these are expected to be installed globally; the report simply surfaces what is present and how it compares upstream.

## Requirements
- Python 3.9+
- Network access to query GitHub/PyPI/crates.io/npm

## Quick Start

```bash
python3 cli_audit.py | column -s '|' -t
```

Tip: On systems where `column` is unavailable, just view the raw output or import into your tool of choice.

## Quick agent readiness check

- Table scan for a quick look:

```bash
python3 cli_audit.py | column -s '|' -t
```

- JSON for actionable filtering (e.g., list anything not up to date):

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py \
  | jq -r '.[] | select(.status != "UP-TO-DATE") | [.tool, .status] | @tsv'
```

- Typical remediation workflow for agent readiness:
  1. Run the audit.
  2. Install or update missing/outdated tools using the `make install-*` targets under Installation scripts (or your package manager).
  3. Re-run the audit until only up-to-date tools remain.

## Extending the Tool List
Agent-focused tools live in the `TOOLS` tuple in `cli_audit.py`. Prefer upstreams with discoverable latest releases:

```python
Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd")),
```

- `name`: logical name displayed in output
- `candidates`: executable names to search on PATH (first line of their version output is used)
- `source_kind`: one of `gh`, `pypi`, `crates`, `npm`, or `skip`
- `source_args`: parameters for the source (e.g., owner/repo for GitHub, package name for PyPI/crates/npm)

If `source_kind` is `skip`, upstream lookup is disabled for that tool.

## Notes and Caveats
- Timeouts are kept intentionally short (3s) to avoid blocking; transient network failures may mark `latest_upstream` as empty.
- When multiple candidates are installed, the highest semantic version is selected.
- For tools without a conventional version flag, the script tries a small set of common flags and a few special cases.

### Debugging

- Set `CLI_AUDIT_DEBUG=1` to print brief debug messages for suppressed exceptions and best-effort operations (e.g., uv tool enumeration). Disabled by default.

### Empty selection handling

- When selecting tools via `--only` or `CLI_AUDIT_ONLY`, unknown names now yield an empty JSON array in JSON mode and a header-only table in text mode.

## Development

- Lint (optional):
```bash
python3 -m pyflakes cli_audit.py
```

- Run tests (n/a): This repo currently ships without tests. PRs welcome.

## Installation scripts

Language-agnostic core tools and language-specific stacks are provided under `scripts/`:

```bash
make scripts-perms

# Core simple tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
make install-core

# Language stacks
make install-python
make install-node
make install-go

# Higher-level tools
make install-aws
make install-kubectl
make install-terraform
make install-ansible
make install-docker
make install-brew
make install-rust
```

These scripts prefer the most up-to-date sources (e.g., nvm for Node, vendor installers for AWS CLI and kubectl) when feasible.

### Install-method classification (how local tools are attributed)

The audit attempts to identify how a tool was installed by inspecting the resolved executable path and environment hints. Recognized classifications include (non-exhaustive):

- `uv tool`, `uv python`, `uv venv`
- `pipx/user`
- `npm (user)`, `npm (global)`, `corepack`, `nvm/npm`
- `asdf`, `nodenv`, `pyenv`, `rbenv`
- `homebrew` (Linuxbrew/macOS), `/usr/local/bin`, `apt/dpkg`, `snap`
- `rustup/cargo`, `go install`, `pnpm`, `yarn`, `pnpm`
- `volta`, `sdkman`, `nodist`

When ambiguous, the audit may report a generic bucket (e.g., `~/.local/bin`). The JSON output includes `installed_path_resolved` and `classification_reason` to aid debugging.

### Actions: install, update, uninstall, reconcile

All scripts accept an action argument. Defaults to `install`.

```bash
# Update existing toolchains
make update-core
make update-python
make update-node
make update-go
make update-aws

# Uninstall
make uninstall-node

# Reconcile preferred method
# Example: remove distro Node and switch to nvm-managed
make reconcile-node

# Example: remove distro Rust and switch to rustup-managed
make reconcile-rust
```

## Caching

- Manual baseline (committed): `latest_versions.json` in this repo (override with `CLI_AUDIT_MANUAL_FILE`). Used as the primary source in offline mode; also used as a fallback when online lookups fail. Example content:

```json
{
  "rust": "1.89.0",
  "jq": "jq-1.8.1",
  "parallel": "20240322"
}
```

- Auto-updates: when an online lookup succeeds, the tool writes the discovered latest value back into `latest_versions.json` (toggle with `CLI_AUDIT_WRITE_MANUAL=0`).
- Offline behavior: set `CLI_AUDIT_OFFLINE=1` to use `latest_versions.json` exclusively.

### Lookup hints

To speed up future runs, the audit records which upstream retrieval method worked last per tool. These hints are stored inside `latest_versions.json` under the special key `"__hints__"`. They help prioritize the fastest working method on subsequent runs and are safe to edit or remove; they will be rebuilt.

## License
MIT
