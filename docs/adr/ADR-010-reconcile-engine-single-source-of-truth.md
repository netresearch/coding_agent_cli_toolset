# ADR-010: Reconcile Engine as Single Source of Truth for Duplicate-Install Cleanup

**Status:** Accepted
**Date:** 2026-07-23
**Deciders:** AI CLI Preparation Team
**Tags:** reconciliation, cli, safety, makefile
**Builds on:** ADR-009 (first-class multi-install data model), ADR-002
(package-manager preference policy — consumed here, not redefined)

## Context

The removal engine `cli_audit/reconcile.py` (preference ranking,
aggressive/parallel modes, version + `active` marker, and the
`SYSTEM_TOOL_SAFELIST` critical-tools protect list) existed but was not
reachable from the user-facing surfaces:

- `guide.sh`'s duplicate warning was a listing-only view built on the thin
  shell `detect_all_installations` (`scripts/lib/capability.sh`) — no
  versions, no indication which install actually runs, no cleanup action.
- `make reconcile-<tool>` called the install-script `reconcile` action rather
  than the Python engine.
- `make upgrade-managed` / `upgrade-all` silently moved tools past the
  versions pinned in `pins.json` and any project lockfiles.

ADR-009 established multi-install as a first-class concern and warned against
a "parallel detection universe" in shell. This decision (design approved
2026-07-08, implemented in `guide.sh`, `audit.py`, `Makefile.d/user.mk`,
`scripts/auto_update.sh`) records how the engine was surfaced.

## Decision

1. **Single source of truth.** `cli_audit/reconcile.py` owns multi-install
   listing, the active/preferred markers, and removal planning. All shell
   surfaces (guide, make targets) consume it through the
   `audit.py --reconcile [<tool>|--all] [--apply] [--yes]` JSON entrypoint
   (`CLI_AUDIT_JSON=1`). Detection is never re-implemented in shell; the shell
   `detect_all_installations` remains only as a cheap pre-check.

2. **Safety model: confirm-each + dry-run.**
   - Nothing is removed without an explicit `y`; `make reconcile-all`
     confirms per tool; `make reconcile-all-dry-run` previews and removes
     nothing.
   - Removing the **active** install prints an extra heads-up naming the
     binary that will run afterwards.
   - The `SYSTEM_TOOL_SAFELIST` protect list is **always** honored:
     `FORCE=1` / `--yes` bypass prompts, never the protect list. Protected
     duplicates are listed but not removed.

3. **Pin/lock override warning.** `upgrade-managed` / `upgrade-all` print a
   warning + `Continue?` prompt before running native manager upgrades,
   because those upgrades move tools past `pins.json` and project lockfiles
   (pins are NOT enforced there). Bypassed only by `FORCE=1` or `--dry-run`.

4. **Discoverability hints are advisory.** Hints (`→ make reconcile-all` when
   duplicates exist; `→ make upgrade-managed`) are printed only when relevant
   and never block.

## Alternatives Considered

- **Enriching the shell `detect_all_installations`** — rejected: duplicates
  the Python engine, recreating the parallel detection universe ADR-009
  warned about.
- **Automatic/batch removal without per-tool confirmation** — rejected:
  removal is destructive; explicit confirmation per tool is required.

## Consequences

**Positive:**
- One engine; guide and make targets render the same plan.
- ADR-009's aggressive reconcile is user-reachable (`make reconcile-all`,
  guide option `c`).

**Negative:**
- The guide gains a Python-process dependency per duplicate-listing render.

**Follow-ups:**
- ADR-009 status note that aggressive reconcile is now user-reachable.

## References

- Design spec (removed after conversion to this ADR):
  `docs/superpowers/specs/2026-07-08-reconcile-and-upgrade-discoverability-design.md`
- `scripts/guide.sh` (`check_multi_installs`), `Makefile.d/user.mk`
  (`reconcile-all`, `reconcile-all-dry-run`), `scripts/auto_update.sh`
  (pin/lock warning), `audit.py` (`--reconcile`)
