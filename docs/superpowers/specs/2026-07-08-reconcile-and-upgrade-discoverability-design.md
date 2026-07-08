# Design: Multi-install cleanup + upgrade discoverability

**Date:** 2026-07-08
**Status:** Approved (pre-implementation)
**Related:** [ADR-009 first-class multi-install](../../adr/ADR-009-first-class-multi-install.md),
[ADR-002 package-manager-hierarchy](../../adr/ADR-002-package-manager-hierarchy.md),
[ADR-003 parallel-installation](../../adr/ADR-003-parallel-installation-approach.md)

## Context

Two user needs surfaced from real `make upgrade` runs:

1. **Bulk-upgrade discoverability.** A command to run every package manager's own
   full upgrade already exists — `make upgrade-managed` / `make upgrade-all`,
   backed by `scripts/auto_update.sh` (18 managers incl. `gup`, `composer`,
   `poetry`, `cargo`/`rustup`, `uv`/`pip`/`pipx`, `npm`/`pnpm`/`yarn`). It is not
   discoverable from the `update`/`upgrade` flow, and it does not warn that
   running managers' native upgrades moves tools past the versions this tool
   pins (`pins.json`) and any project lockfiles.

2. **Multi-install cleanup.** `guide.sh`'s `check_multi_installs()` detects
   duplicate installs (e.g. `git-absorb` at `~/.local/bin` **and**
   `~/.cargo/bin`) and prints a `⚠️` warning, but:
   - the listing shows only `method: path` — no version, and no indication of
     which install actually runs when the command is called without a path;
   - it offers no action to remove the redundant install;
   - the removal engine that *does* exist (`cli_audit/reconcile.py`, with
     parallel/aggressive modes, version + `active` marker, preference ranking,
     and a critical-tools protect list) is not reachable from the guide, and
     `make reconcile-<tool>` calls the install-script `reconcile` action rather
     than `reconcile.py`.

ADR-009 already establishes multi-install as a first-class concern and notes
`reconcile.py` "exists solely to delete duplicates" and re-scans from scratch.
This design surfaces that engine and closes the discoverability gaps.

## Goals

- Make `reconcile.py` the single source of truth for multi-install listing,
  the active/preferred markers, and removal planning.
- Show version + active + preferred per install in the guide's warning.
- Offer inline cleanup in the guide, and a `make reconcile-all` sweep.
- Add discoverability hints and a pin/lock override warning.

## Non-goals

- No change to how single-install tools are audited/upgraded.
- No new package-manager coverage in `auto_update.sh` (already comprehensive).
- No automatic removal without explicit confirmation (see Safety model).
- No change to ADR-002 preference policy (vendor/user-level wins); this design
  consumes it, it does not redefine it.

## Design

### Component 1 — Richer multi-install listing (source of truth: reconcile.py)

`reconcile.py` already computes, per install, `Installation.version`,
`Installation.path`, `Installation.active` (the `which()`-resolved binary — the
"default when called without a path"), and `preference_score`; `reconcile_tool()`
yields the `preferred` install. A new JSON CLI entrypoint (Component 6) exposes
this. `check_multi_installs()` in `guide.sh` switches from the thin shell
`detect_all_installations` (`scripts/lib/capability.sh`) to this data and renders:

```
⚠️  Multiple installations detected (2):
   • yq 4.44.3  manual  /home/sme/.local/bin/yq   → active  ✓ keep
   • yq 4.40.1  manual  /usr/local/bin/yq
```

- `→ active` marks the PATH-resolved install (`Installation.active`).
- `✓ keep` marks the preferred install reconcile would retain.
- When `active` and `keep` are **different** installs, print one extra line:
  `note: cleanup would change which yq runs (active → preferred).`
- Version per install comes from reconcile's detection; if a version can't be
  read, show `?` rather than suppressing the row.

### Component 2 — Inline cleanup action in the guide (#3)

When `check_multi_installs()` reports >1 install, the guide's option list gains:

```
c = clean up duplicates (keep preferred, remove the rest)
```

Selecting `c`:
1. Prints the keep/remove plan (reuses Component 1 rendering).
2. Confirms (per Safety model). Removing the **active** install prints an extra
   heads-up naming the new active binary.
3. Calls `reconcile_tool(..., mode="aggressive")` for that tool.
4. Re-audits and reloads JSON (same pattern as the existing update path).

Single-install tools never show option `c`. Critical tools (reconcile.py protect
list) show the plan but decline to remove, with a reason line.

### Component 3 — `make reconcile-all` (#4)

Sweeps all installed tools, selects those with >1 install, and reconciles each
via `bulk_reconcile()` in aggressive mode. Per the Safety model it shows the plan
and confirms **per tool** before removing. Targets:

- `make reconcile-all` — interactive confirm-each.
- `make reconcile-all-dry-run` — preview only, removes nothing (`DRY_RUN=1`).

Wraps `cli_audit/reconcile.py::bulk_reconcile`; honors the critical-tools protect
list; reports a summary (reconciled / skipped / protected / failed).

### Component 4 — Discoverability hints (#1)

After the `make update` / `make upgrade` / guide summary, print 1–2 lines **only
when relevant**:

- If any tool has duplicate installs:
  `N tool(s) have duplicate installs → make reconcile-all`
- `Upgrade the package managers themselves → make upgrade-managed`: shown in the
  audit summary when outdated tools exist, and always in the interactive
  upgrade (guide) summary footer.

Hints are informational, never block, and are suppressed when nothing applies
(no duplicates → no reconcile hint).

### Component 5 — Pin/lock override warning (#2)

`make upgrade-managed` / `upgrade-all` print before running native manager
upgrades:

```
⚠️  This runs each package manager's own upgrade. It moves tools PAST the
    versions pinned in cli-audit (pins.json) and any project lockfiles —
    pins are NOT enforced here.
Continue? [y/N]
```

- Bypass with `FORCE=1` (non-interactive/CI) or when `--dry-run`.
- Emitted once per invocation, before the first manager runs.
- Lives in `scripts/auto_update.sh` (or its Make wrapper), guarded so
  `upgrade-all-dry-run` never prompts.

### Component 6 — reconcile.py JSON CLI entrypoint (enabler)

Add a `reconcile` subcommand to `audit.py` exposing `reconcile.py`:

- `audit.py reconcile <tool> --plan --json` → `{installations:[{version,method,
  path,active,preferred}], preferred, active, protected}` for one tool (feeds
  Components 1 & 2).
- `audit.py reconcile --all --plan --json` → same, per tool with >1 install
  (feeds Component 3).
- `audit.py reconcile <tool> --apply [--yes]` / `--all --apply` → performs
  aggressive reconciliation (feeds the actual removal in Components 2 & 3).

`CLI_AUDIT_JSON=1` conventions and existing snapshot reuse apply. This entrypoint
is the seam that lets shell surfaces (guide, make targets) consume the Python
engine without re-implementing detection.

## Safety model (chosen: confirm-each + dry-run)

- Nothing is removed without an explicit `y`.
- `make reconcile-all` confirms **per tool**; `reconcile-all-dry-run` previews.
- Removing the **active** install prints an extra heads-up (what will run after).
- Critical-tools protect list (`reconcile.py`) is always honored; protected
  duplicates are listed but never removed.
- `FORCE=1` / `--yes` bypass prompts for CI, but respect the protect list.

## Data flow

```
reconcile.detect_installations(tool)
  → [Installation(version, path, active, preference_score)]
  → sort_by_preference()  → preferred
  → audit.py reconcile --json  (Component 6)
      → guide.sh check_multi_installs()   render (C1) + option 'c' (C2)
      → make reconcile-all  → bulk_reconcile()  (C3)
  → reconcile_tool(mode="aggressive")  → _uninstall_installation()  (removal)
```

## Files touched (anticipated)

- `cli_audit/reconcile.py` — plan/JSON marks each install's `preferred` boolean
  (derived from `ReconciliationResult.preferred` + `Installation.active`); no
  engine rewrite.
- `audit.py` — new `reconcile` subcommand (Component 6).
- `scripts/guide.sh` — `check_multi_installs()` rendering (C1), option `c` (C2),
  summary hints (C4).
- `scripts/auto_update.sh` — pin/lock override warning (C5).
- `Makefile.d/user.mk` — `reconcile-all`, `reconcile-all-dry-run` targets;
  `.PHONY` list.
- `docs/adr/ADR-009-*` — status note that aggressive reconcile is now
  user-reachable (follow-up, not blocking).

## Testing

- **Unit (`cli_audit`):** plan output with active ≠ preferred; critical-tool
  protection (listed, not removed); single-install → empty plan; `--all` selects
  only multi-install tools; JSON shape.
- **Shell (`tests/test_guide_multi_install.sh`):** listing shows version +
  `→ active` + `✓ keep`; option `c` appears only with duplicates; confirm/decline
  paths (mocked removal).
- **Make target:** `reconcile-all-dry-run` removes nothing and lists a plan;
  `FORCE=1` path is non-interactive.
- **Regression:** existing single-install and up-to-date paths unchanged.
