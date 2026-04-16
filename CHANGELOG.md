# Changelog

All notable changes to this project are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Governance files: `SECURITY.md`, `CODEOWNERS`, PR template, `CHANGELOG.md`.
- `.github/workflows/codeql.yml`, `scorecard.yml`, `dependency-review.yml` for supply-chain scanning.
- `.pre-commit-config.yaml` for local hook enforcement.
- README badges (CI, Codecov, License).
- AGENTS.md structural sections (Commands, Setup, Testing, Architecture, Development).
- Per-cycle `auto_update` storage for multi-version tools (`python@3.13` vs `python@3.14`).
- Persistent endoflife.date cache at `~/.cache/cli-audit/endoflife.json` with fallback on HTTP failure.
- Binary-probe fallback in `guide.sh` when the post-install snapshot refresh is stale.

### Fixed
- `cmd_update_local` in MERGE mode now refreshes multi-version cycle entries (`python@3.14`, …) instead of only the base-tool entry. Resolved false-negative "Upgrade did not succeed" messages after successful uv installs.

### Changed
- Upgraded 23 locked Python dev-dependencies to latest compatible versions (bandit 1.9.4, mypy 1.20.1, isort 8.0.1, rich 15.0, coverage 7.13.5, …).

## Prior history

See [git log](https://github.com/netresearch/coding_agent_cli_toolset/commits/main) for commits prior to this changelog. Tagged releases: [Releases page](https://github.com/netresearch/coding_agent_cli_toolset/releases).
