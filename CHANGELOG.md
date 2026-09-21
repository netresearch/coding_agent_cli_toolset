# Changelog

All notable changes to this project are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `herdr` catalog entry (`catalog/herdr.json`): terminal multiplexer for coding agents, installed as a raw linux binary from GitHub releases (x86_64, aarch64) with bash completion.
- `wslu`/`wslview` catalog entry (`catalog/wslu.json` + `scripts/install_wslu.sh`), gated by a new `requires_wsl` catalog flag so it is only surfaced and installed under WSL. Its installer also points the xdg default browser at `wslview` (so links open in the Windows browser); opt out with `WSLU_SET_DEFAULT_BROWSER=0`.
- Governance files: PR template, `CHANGELOG.md`. Security reporting is covered by the [org-level SECURITY.md](https://github.com/netresearch/.github/blob/main/SECURITY.md).
- `.github/workflows/dependency-review.yml` and a dedicated `security.yml` (pip-audit + bandit + CycloneDX SBOM). CodeQL continues to run via GitHub's default code-scanning setup.
- `.pre-commit-config.yaml` for local hook enforcement (flake8, black, isort, shellcheck).
- README badges: CI, License.
- AGENTS.md structural sections (Commands, Setup, Testing, Architecture, Development).
- Per-cycle `auto_update` storage for multi-version tools (`python@3.13` vs `python@3.14`).
- Persistent endoflife.date cache at `~/.cache/cli-audit/endoflife.json` with fallback on HTTP failure.
- Binary-probe fallback in `guide.sh` when the post-install snapshot refresh is stale.

### Fixed
- difftastic 0.71.0 puts the version into its release file names (`difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz`); the catalog download URL now includes it. byobu is tagged `trustmux-v7.19` since the trustmux rename, and those tags fill the first page of the tags API, so the installer found no stable tag; it now accepts both tag forms.
- `make upgrade` auto-update no longer reports an upgrade as "Updated" just because the install script exited 0. The version is compared after the re-audit, the same check the interactive `Y`/`a` answers use; an unchanged version counts as "Failed" with the old and target version. A package manager without a newer package (`bwrap` on apt) and a binary identical to the target release with a stale version string (`sd` 1.1.0 reports 1.0.0) count as "Skipped". "Held back" requires the package manager to confirm it: a failed install or a newer candidate that did not take effect counts as "Failed".
- `cmd_update_local` in MERGE mode now refreshes multi-version cycle entries (`python@3.14`, …) instead of only the base-tool entry. Resolved false-negative "Upgrade did not succeed" messages after successful uv installs.

### Changed
- Upgraded 23 locked Python dev-dependencies to latest compatible versions (bandit 1.9.4, mypy 1.20.1, isort 8.0.1, rich 15.0, coverage 7.13.5, …).

## Prior history

See [git log](https://github.com/netresearch/coding_agent_cli_toolset/commits/main) for commits prior to this changelog. Tagged releases: [Releases page](https://github.com/netresearch/coding_agent_cli_toolset/releases).
