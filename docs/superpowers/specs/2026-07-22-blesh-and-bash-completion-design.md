# Design: ble.sh tool + bash-completion installation support

**Date:** 2026-07-22
**Status:** Approved (design), pending implementation
**Delivery:** Two independent PRs

## Problem

1. **ble.sh** (Bash Line Editor — syntax highlighting, autosuggestions, richer
   completion UI for interactive Bash) is not in the catalog. It should be
   installable/upgradable/removable through the standard `make install-blesh`
   flow.
2. The toolset installs many CLIs but never installs their **bash completion**
   scripts, so tab-completion for `gh`, `glab`, `uv`, `rg`, etc. is missing.
   We want completions installed automatically as part of a tool's lifecycle,
   plus a way to backfill completions for tools already installed.

These are thematically related (interactive-shell ergonomics) but technically
independent, so they ship as **two PRs**.

---

## PR 1 — Add ble.sh

ble.sh is *sourced* into an interactive shell, not placed on `PATH` as a
binary. Recommended upstream install is `git clone --recursive` +
`make install PREFIX=~/.local`, then a `source` line in `.bashrc`. This matches
the repo's `dedicated_script` pattern (cf. `install_tmux.sh`, built from source).

### Catalog: `catalog/blesh.json`

```jsonc
{
  "name": "blesh",
  "category": "general",
  "install_method": "dedicated_script",
  "script": "install_blesh.sh",
  "description": "Bash Line Editor — full-featured line editor for interactive Bash (syntax highlighting, autosuggestions, completion UI)",
  "homepage": "https://github.com/akinomyoga/ble.sh",
  "github_repo": "akinomyoga/ble.sh",
  "binary_name": "ble.sh",
  "version_command": "bash \"$HOME/.local/share/blesh/ble.sh\" --version 2>/dev/null",
  "notes": "Not a PATH binary — sourced from ~/.local/share/blesh/ble.sh via .bashrc. Built from source (git clone --recursive + make install). Requires git, make, gawk.",
  "tags": []
}
```

**Unknowns — RESOLVED with evidence (2026-07-22, real install into a scratch prefix):**

- **Installed-version detection.** ✅ `bash "$HOME/.local/share/blesh/ble.sh"
  --version` prints `ble.sh (Bash Line Editor), version 0.4.0-devel4+d69e4d5`
  (exit 0). `version_command` runs via `shell=True`, and detection falls back to
  the standalone `<version_command>` path when no PATH binary is found (ble.sh's
  `binary_name` is never on PATH). `extract_version_number(...)` yields `0.4.0`.
  No `version_regex` needed (not a real catalog field — unused in code).
- **Upstream version tracking.** ✅ `collect_github('akinomyoga','ble.sh')`
  returns `('v0.4.0-devel3', '0.4.0')` via the `/releases/latest` redirect —
  the `nightly` tag does not pollute it. Installed `0.4.0-develN` and upstream
  both normalize to `0.4.0` and align. **No `skip_upstream` needed.** The
  installer clones the default (`master`) branch, matching upstream detection.

### Installer: `scripts/install_blesh.sh`

Structure mirrors `install_tmux.sh`. Supports `install` | `update` | `uninstall`.

- **Deps check:** ensure `git`, `make`, `gawk` (ble.sh needs gawk). Install via
  apt (with `sudo`) only if missing, same pattern as `install_tmux.sh`.
- **install/update:**
  - Clone to a fixed source dir (e.g. `~/.local/src/ble.sh`) with
    `git clone --recursive --depth 1 --shallow-submodules`; if already present,
    fetch/reset like `github_clone.sh` does.
  - `make -C <src> install PREFIX="$HOME/.local"` → installs to
    `~/.local/share/blesh/`.
  - Idempotently ensure a **single managed block** in `~/.bashrc`:
    ```bash
    # >>> cli-audit: ble.sh >>>
    [[ $- == *i* ]] && source ~/.local/share/blesh/ble.sh
    # <<< cli-audit: ble.sh <<<
    ```
    Guarded by the delimiter comments; never appended twice.
  - Report before/after version; call `refresh_snapshot "$TOOL"`.
- **uninstall:** remove `~/.local/share/blesh/`, the source dir, and the managed
  `.bashrc` block (delete the delimited region only — never rewrite unrelated
  lines).

### Tests (PR 1)

- Catalog validity test already iterates `catalog/*.json`; `blesh.json` must
  pass its schema assertions (valid `install_method`, referenced `script`
  exists and is executable).
- Add a focused assertion (pytest or `test_smoke.sh`) that
  `install_blesh.sh` prints usage for an unknown action and that its
  `.bashrc`-block insertion is idempotent (run the insert helper twice → one
  block). Network/clone is **not** exercised in CI.

### Docs (PR 1)

- Regenerate / update `catalog/CATALOG_SUMMARY.md` and `catalog/COVERAGE.md`
  if they are generated from the catalog; otherwise add the `blesh` row.

---

## PR 2 — Bash-completion installation framework

### Catalog schema: optional `bash_completion`

Add an **optional** object to any catalog entry. Two shapes:

```jsonc
// Shape A — generate to stdout (most modern CLIs)
"bash_completion": { "command": "gh completion -s bash" }

// Shape B — copy a file shipped inside the tool's install/clone
"bash_completion": { "source_path": "shell/completion.bash" }
```

- Absent field ⇒ tool has no bash completion (or none worth shipping).
- `command` is run with the tool on `PATH`; stdout is captured.
- `source_path` is resolved relative to the tool's install/clone dir.
- Schema is additive and backward-compatible; existing entries unaffected.

### Installer lib: `scripts/lib/completion.sh`

Pure functions, sourced by the orchestrator and the make targets:

- `completion_dir()` → `${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions`
- `install_completion <tool>`:
  1. Read `.bash_completion` from `catalog/<tool>.json`; no field ⇒ no-op (0).
  2. Shape A: run `command`, capture stdout to a temp file.
     Shape B: locate `source_path`, copy to temp file.
  3. **Validate** the captured output is non-empty and looks like a bash
     completion script (e.g. contains `complete ` or `_<tool>` / `compgen`);
     refuse to install garbage. Log and return non-zero on validation failure.
  4. Move into `completion_dir()/<tool>`.
- `remove_completion <tool>`: delete `completion_dir()/<tool>` if present.
- `ensure_bash_completion_framework`:
  - Ensure the `bash-completion` package is installed (apt, best-effort with
    `sudo`; skip silently if unavailable/no sudo).
  - Ensure a **single managed block** in `~/.bashrc` sources the framework
    loader if the distro doesn't already (`/usr/share/bash-completion/bash_completion`),
    same delimiter-guard technique as ble.sh.
  - Called once before writing any completion file.

All completion operations are **best-effort**: a failure logs a warning and
returns non-zero but must **never** abort or fail the tool install/uninstall
that invoked it.

### Entry point: `scripts/install_completion.sh`

Thin CLI wrapper: `install_completion.sh <tool> [install|remove]` → sources the
lib and dispatches. Used by make targets and callable standalone.

### Lifecycle hooks: `scripts/install_tool.sh`

- After a **successful** `install`/`update`/`reconcile` of a tool, call
  `ensure_bash_completion_framework` (once) then `install_completion <tool>`
  — guarded so failure only warns.
- In the `uninstall` path, call `remove_completion <tool>`.
- Hooks are additive; they wrap existing success/exit points without changing
  current control flow or exit codes.

### Make targets

In `Makefile.d/user.mk` (+ `.PHONY` in `Makefile`):

- `make completions` — for every **installed** tool (per `local_state.json`)
  that declares `bash_completion`, run `install_completion`. Ensures the
  framework first. This is the backfill for pre-existing installs.
- `make completion-<tool>` — (re)install completion for one tool.

### Coverage — broad sweep (this PR)

Audit **all** catalog entries and declare `bash_completion` for every tool that
supports it:

- Classify each tool as **command** / **source_path** / **none**.
- For `command` tools, use the tool's real, documented generator (verified by
  running it where the tool is installed locally; otherwise from official docs).
  Common conventions: `<tool> completion bash`, `<tool> completion -s bash`,
  `<tool> --completion bash`, `<tool> generate-shell-completion bash`,
  `<tool> --generate complete-bash`. **Do not assume** a convention — verify
  per tool.
- Record the classification result (tool → mechanism / none) in
  `catalog/COVERAGE.md` so coverage is auditable.

**Scope note:** the broad sweep makes PR 2 exceed the repo's ~300 net-LOC
guideline. This is a deliberate, accepted trade-off (chosen over a curated
subset); the framework code stays small and the bulk is mechanical, additive,
per-tool JSON plus a coverage table.

### Tests (PR 2)

- Unit test `install_completion` against a **fake tool** fixture for both
  shapes (command via a stub script that echoes a known completion; source_path
  via a fixture file) — assert the file lands in a temp `XDG_DATA_HOME` and that
  validation rejects empty/garbage output.
- Test `remove_completion` deletes the file and is a no-op when absent.
- Test the `.bashrc` managed-block insert is idempotent.
- Test that `bash_completion` values in the catalog are schema-valid (object
  with exactly one of `command` | `source_path`) — extend the catalog-validity
  test.
- No network; no real tool execution in CI (use stubs/fixtures).

---

## Non-goals / YAGNI

- No zsh/fish completion (bash only, per request).
- No completion for tools that don't natively provide one (no hand-written
  completion scripts maintained in-repo).
- No auto-refresh daemon; refresh is explicit (`make completions`) or happens
  on the next install/upgrade of a tool.

## Risks

- **ble.sh version detection / upstream parsing** — RESOLVED with evidence from
  a real scratch install (see PR 1 section); no residual risk.
- **bash-completion framework absence** — mitigated by
  `ensure_bash_completion_framework`; on systems without apt/sudo it degrades to
  a warning and the XDG files still work once a framework is present.
- **Wrong generator command per tool** — mitigated by output validation before
  install and by verifying each generator during the broad sweep.
