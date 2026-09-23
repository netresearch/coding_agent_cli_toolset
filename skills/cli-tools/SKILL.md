---
name: cli-tools
description: "Use when a command fails with 'command not found', when installing, updating or removing CLI tools (ripgrep, fd, jq, yq, bat, gh, …), when auditing what a project or machine has installed, or when choosing a modern tool over a legacy one (rg over grep -r, fd over find, jq over grep on JSON). Triggers on: command not found, install tool, missing binary, environment audit, update tools, duplicate installation, which, apt install, brew install."
license: "(MIT AND CC-BY-SA-4.0)"
compatibility: "Requires bash 4+ and jq. The Python audit (audit.py) additionally needs uv."
metadata:
  repository: "https://github.com/netresearch/coding_agent_cli_toolset"
  author: "Netresearch DTT GmbH"
---

# CLI Tools

Install, audit, update and reconcile CLI tools from the toolset's catalog
(`catalog/<tool>.json`, one entry per tool). The skill ships inside that
repository; every script named below lives in `${CLAUDE_SKILL_DIR}/../../scripts/`
— call it by that path, never by a copy.

## Missing tool (`command not found`)

1. **Diagnose first**: `type -P -a <binary>`, then `hash -r`. It may already be
   installed off PATH (`~/.local/bin`, `~/.cargo/bin`, `$(go env GOPATH)/bin`).
2. **Map binary to catalog name** with `references/binary_to_tool_map.md`
   (`rg` → `ripgrep`, `ansible` → `ansible-core`, `difft` → `difftastic`), or
   `jq -r 'select(.binary_name == "<binary>") | input_filename' ${CLAUDE_SKILL_DIR}/../../catalog/*.json`.
3. **Install**: `${CLAUDE_SKILL_DIR}/../../scripts/install_tool.sh <tool> install`
4. **Verify**: `type -P <binary>` and `<binary> --version`.

Full flow: `references/resolution-workflow.md`.

## Actions

`${CLAUDE_SKILL_DIR}/../../scripts/install_tool.sh <tool> <action>` with action
`install` (default), `update`, `uninstall`, `reconcile` (switch to the preferred
install method and remove the other copy) or `status`.

## Environment audit

- `${CLAUDE_SKILL_DIR}/../../scripts/check_environment.sh audit <project_dir>` —
  PATH problems, duplicate installations, package managers, required tools
- `${CLAUDE_SKILL_DIR}/../../scripts/detect_project_type.sh json <project_dir>` —
  project types plus required and recommended catalog tools

Per-type tool lists and the tools that belong in the project rather than on the
machine (phpstan, mypy, …): `references/project_type_requirements.md`.

## Batch update

`${CLAUDE_SKILL_DIR}/../../scripts/auto_update.sh update` updates every detected
package manager and its packages; prefix `DRY_RUN=1` to preview.

## Preferred modern tools

| Legacy | Modern | Legacy | Modern |
|--------|--------|--------|--------|
| `grep -r` | `rg` | `diff` | `difft` |
| `find` | `fd` | `time` | `hyperfine` |
| grep on JSON | `jq` | `cat` | `bat` |
| sed on YAML | `yq` | `cloc` | `tokei` / `scc` |
| awk on CSV | `qsv` | grep for security | `semgrep` |
| sed on TOML | `dasel` | | |

Install commands and per-tool gotchas: `references/preferred-tools.md`.

## Cold start

The shell scripts need only bash and jq, so they work straight from a fresh
plugin install. Without the Python environment two things degrade, neither
fatal: the user config (`~/.config/cli-audit/config.yml`) falls back to its
defaults, and the audit snapshot is not refreshed after an install
(`# Warning: Failed to refresh snapshot`). `audit.py` itself (the version
table, `make audit`) does need that environment: run it as
`uv run --project ${CLAUDE_SKILL_DIR}/../.. python ${CLAUDE_SKILL_DIR}/../../audit.py`,
which creates one on first use.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Installed but not found | `hash -r`, or add the install dir to PATH |
| No sudo | `cargo install`, `uv tool install`, a release binary; on Debian/Ubuntu `apt-get download` + `dpkg -x` |
| Debian `bat` = `batcat`, `fd` = `fdfind` | symlink into `~/.local/bin/` |
| Global npm install lands off PATH | a `node` shim ahead of nvm — see troubleshooting |

PATH, permissions, portability (`timeout` on macOS) and probe pitfalls:
`references/troubleshooting.md`.

## Shell pitfalls

Before trusting a status, a count or an empty result from a shell command,
check `references/shell-pitfalls.md`: `set -e` with `$(…)`, SIGPIPE under
`pipefail`, `read`/`IFS` field collapse, heredoc and quoting traps, `sed -i`
no-ops — and that `grep` in the agent's shell is ugrep, which skips
`.gitignore`d files and gets `grep -q -v` wrong.
