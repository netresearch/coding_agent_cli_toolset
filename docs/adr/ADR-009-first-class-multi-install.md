# ADR-009: First-class support for multiple installations of the same tool

**Status:** Proposed
**Date:** 2026-04-21
**Deciders:** AI CLI Preparation Team
**Tags:** detection, audit, upgrade, pinning, reconciliation
**Supersedes-in-part:** ADR-003 (parallel installation) for the *data model*
only — the user-facing policy from ADR-003 (keep both, prefer user-level via
PATH) is preserved and extended.

## Context

The catalog can have several binaries of the same tool on a machine — e.g.
`/usr/bin/ripgrep` (apt, 14.0.0) next to `~/.cargo/bin/rg` (cargo, 14.1.1).
ADR-003 already says we keep both. The implementation does not.

Current reality:

- `audit_tool_installation()` (`cli_audit/detection.py:299`) discovers all
  candidate paths in `PATH` when invoked with `deep=True`, but then calls
  `choose_highest()` and returns **a single 4-tuple**
  `(version, line, path, method)`.
- The snapshot writer (`audit.py`) records the chosen path as
  `installed_path_selected` / `installed_method`. The other installs are
  dropped before the snapshot is persisted.
- `make audit`, `make upgrade`, and the pin system all operate on a single
  `tool` key — they cannot address "the apt ripgrep" vs "the cargo
  ripgrep" separately.
- The only place the rest of the installations exist is
  `cli_audit/reconcile.py`, which re-scans from scratch and exists solely
  to *delete* duplicates.

Effect on the user:

- `make audit` reports one row per tool. If the PATH-preferred install is
  up-to-date, the row is green; a second, stale install behind it is
  invisible.
- `make upgrade <tool>` only upgrades the PATH-preferred install. If an
  apt copy is also on disk, it stays at whatever apt has.
- `scripts/pin_version.sh <tool> <version>` pins the name, not the install
  — a user cannot say "pin the apt one, keep cargo rolling".
- The `notes` column added in the companion change can say `apt · PIN:1.0`
  but only for whichever install won `choose_highest()`.

User position (requirements for this ADR):

1. Multi-install should be discovered and **listed**, not hidden.
2. Each install should be eligible for **update** independently.
3. Each install should be **pinnable** independently.
4. The duplicate itself is a signal worth warning about, but keeping
   duplicates is a legitimate choice; once kept, they must be first-class.

## Decision

Treat each discovered installation of a tool as an individually
addressable record. The tool catalog entry remains the definition of
*what the tool is*; each installation is a concrete *instance* of that
tool on this machine.

### 1. Data model

New dataclass (in `cli_audit/detection.py`):

```python
@dataclass(frozen=True)
class Installation:
    tool: str                 # catalog name, e.g. "ripgrep"
    cycle: str | None         # for multi-version runtimes, e.g. "3.12"
    path: str                 # absolute realpath of the binary
    version: str              # extracted version number
    version_line: str         # raw --version output (diagnostics)
    method: str               # apt|cargo|uv|pipx|brew|nvm|manual|system|…
    is_primary: bool          # first on PATH → the one currently invoked
```

`audit_tool_installation()` is renamed/split:

- `detect_installations(tool, candidates, …) -> list[Installation]`
  returns every hit (no `choose_highest`).
- A thin back-compat wrapper keeps the old 4-tuple for callers that still
  want "the chosen one", implemented as "first `is_primary=True` entry".

### 2. Addressing an installation

Every install has a stable key:

```
<tool>[@<cycle>]#<method>[:<path-hash>]
```

- `ripgrep#apt` — no ambiguity: one apt binary
- `ripgrep#cargo` — the cargo one
- `python@3.12#apt` — apt's python3.12
- `python@3.12#pyenv:abc123` — if two pyenv installs exist, disambiguate
  with a short hash of the realpath

This key appears in the `notes` column, in pin/unpin commands, and in
`make upgrade-<key>`.

### 3. Snapshot schema

`tools_snapshot.json` grows a new field per tool entry:

```json
{
  "tool": "ripgrep",
  "installations": [
    {"path": "/home/u/.cargo/bin/rg", "version": "14.1.1", "method": "cargo",  "is_primary": true},
    {"path": "/usr/bin/rg",           "version": "14.0.0", "method": "apt",    "is_primary": false}
  ],
  "installed":             "14.1.1",        // primary, kept for back-compat
  "installed_method":      "cargo",         //   ''
  "installed_path_selected": "/home/u/.cargo/bin/rg"  // '', to be deprecated
}
```

Legacy `installed_*` fields are kept for one release and marked deprecated
in the schema, then removed.

### 4. Rendering

`make audit` default stays one row per tool, showing the primary. When a
tool has >1 installation the `notes` column appends `+N more` (e.g.
`cargo · +1 more`). A new `--wide` / `CLI_AUDIT_WIDE=1` mode emits one row
per installation with a sub-indented second column
(`  ↳ ripgrep#apt`), so the default view stays narrow but the detail is
reachable without a separate command.

Status semantics per row:

- Primary install: existing `UP-TO-DATE / OUTDATED / NOT INSTALLED`.
- Secondary install: same vocabulary, scoped to that install. The
  tool-level `status` becomes the *worst* of its installs, so a tool with
  one up-to-date and one outdated install is surfaced as `OUTDATED` in
  the summary even if the primary is green.

### 5. Pins

`~/.config/cli-audit/pins.json` extends from

```json
{"ripgrep": "14.1.0"}
```

to optionally accept the `tool#method` key:

```json
{
  "ripgrep":         "14.1.0",        // applies to every ripgrep install
  "ripgrep#apt":     "14.0.0",        // apt-only override
  "ripgrep#cargo":   "never"          // stop touching the cargo one
}
```

Resolution order in `cli_audit/pins.py`:

1. Exact `tool#method[:hash]` match — per-installation pin wins.
2. `tool@cycle` match — existing multi-version behavior.
3. Plain `tool` match — tool-wide default.

Shell helpers (`scripts/pin_version.sh`, `unpin_version.sh`) accept the
`tool#method` form; `reset_pins.sh` is unchanged.

### 6. Upgrade

`upgrade_tool(name)` iterates over every `Installation` whose effective
pin is not `"never"` and whose method has an upgrader. Each install is
upgraded by its own method (apt upgrades apt, cargo upgrades cargo,
etc.). Results are a list:

```
BulkUpgradeResult
  ripgrep#cargo → 14.1.1 → 14.1.2  OK
  ripgrep#apt   → 14.0.0 → 14.0.0  skipped (apt has no newer)
```

`make upgrade-<tool>` stays a convenience that upgrades all installs;
`make upgrade-<tool>#<method>` targets one.

### 7. Reconcile

`reconcile` is no longer the *only* place multi-install exists; it
becomes what its name suggests — a cleanup tool. Its scope narrows to:

- Detect tools with >1 install where the user has *not* pinned the
  duplicate as intentional (`PIN:never` on the non-primary signals "keep
  quiet").
- Offer removal of the non-primary copy.
- Default is dry-run, as today.

### 8. Warnings

On `make audit`, tools with >1 installation get a `⚠ dup` suffix in
notes *unless* every non-primary install is explicitly pinned. The
warning is advisory, not a failure — multi-install is supported, the
warning just makes the situation visible.

## Consequences

**Positive:**

- Hidden stale installs become visible.
- Per-install pinning matches how users actually run into this (apt ships
  old, cargo ships new, both kept deliberately).
- `upgrade_all` stops leaving apt copies behind.
- `reconcile` stops being a parallel detection universe.

**Negative:**

- Snapshot schema bump; one release of legacy fields for transition.
- `audit`, `upgrade`, `pins`, `render`, `reconcile`, `snapshot`,
  `detection`, and the shell helpers all change. Touch-point count is
  the main risk, not individual difficulty.
- `make upgrade-<tool>` semantics change (now multi-target). PR notes
  and CHANGELOG must flag this.

**Neutral:**

- `ADR-003`'s *policy* (keep both, prefer user-level on PATH) is
  unchanged; ADR-009 only upgrades the *implementation* so we can act on
  that policy.

## Open questions

1. **Cycle granularity for multi-version runtimes.** Current pins allow
   `python@3.12` but not `python@3.12#apt`. Do we want three-level keys
   (`python@3.12#pyenv:abc123`)? Likely yes for rigor, but the common
   case is "one runtime per cycle" and the extra depth may be noise.
2. **Version-manager installs (nvm, pyenv, rbenv) as a special case.**
   A pyenv install *is* a family of installs at `~/.pyenv/versions/*`.
   Treat each as its own `Installation`, or treat pyenv as one
   "method" with its own internal cycle list? Leaning toward the former
   (pyenv installs are physical binaries just like apt binaries).
3. **Stable install IDs across reboots.** Realpaths change if a tool is
   symlinked or reinstalled. Use `(method, realpath-basename,
   short-hash)` so the ID is resilient to version bumps but changes
   when the user switches install methods.
4. **Backwards compatibility window.** One release keeping legacy
   `installed_*` fields, or two?

## Rollout

Phased, behind a feature flag to allow incremental landing:

1. Add `Installation` dataclass + `detect_installations()`. Keep
   existing `audit_tool_installation()` as a wrapper returning
   `first_primary`. No behavior change.
2. Extend snapshot with `installations[]`; write both old and new
   fields. `make audit` still reads old fields.
3. Render `+N more` in `notes`; add `--wide` view.
4. Extend pins.json parsing; shell helpers accept `tool#method`.
5. Rewrite `upgrade_tool` to iterate `installations[]`; keep
   single-install path when `len(installations) == 1`.
6. Narrow `reconcile` scope; remove duplicate detection code paths.
7. Drop legacy `installed_*` fields from snapshot schema.

Each step is independently shippable; the flag gate stays until step 5
is proven.
