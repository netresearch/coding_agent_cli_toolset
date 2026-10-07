<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<!-- SPDX-FileCopyrightText: Netresearch DTT GmbH -->

# Security Assurance Case

This document states what users can and cannot expect from AI CLI Preparation (`audit.py`, the `cli_audit` package and the installers under `scripts/`) in terms of security, and argues why the stated requirements are met. Every claim names the file that implements it. The component architecture is described in [ARCHITECTURE.md](ARCHITECTURE.md). Vulnerabilities are reported privately as described in the organisation [security policy](https://github.com/netresearch/.github/blob/main/SECURITY.md).

## What the tool does

The tool runs on the user's own machine, as the user who starts it. It

1. detects which command-line tools are installed and at which version, by running each tool's version command (`cli_audit/detection.py`);
2. looks up the latest upstream version of each tool from public sources: GitHub, GitLab, PyPI, npm, crates.io, the GNU FTP server and endoflife.date (`cli_audit/collectors.py`, `cli_audit/upgrade.py`);
3. on request (`make install-<tool>`, `make upgrade-<tool>`, `make uninstall-<tool>`, `make upgrade`, `audit.py --reconcile --apply`), installs, upgrades or removes tools through the installer scripts in `scripts/` and the system's package managers.

It runs no server and opens no listening port.

## Security requirements

| Id | Requirement |
| --- | --- |
| R1 | In the Python package and `audit.py`, data received from the network or from the output of installed programs is parsed as data and never passed to a shell. |
| R2 | Network requests go to `https://` URLs. In the Python package every request has a timeout. |
| R3 | An API token the user provides (`GITHUB_TOKEN`, `GITLAB_TOKEN`, `GITLAB_PRIVATE_TOKEN`, or the token of the `gh` or `glab` CLI) is sent only to the API of the service it belongs to and is not written to a file or a log. |
| R4 | Configuration files are parsed without executing code. |
| R5 | The tool runs as the invoking user and does not require root. Commands that need root are run through `sudo`, so `sudo`'s password prompt and policy apply. |
| R6 | State and cache files are replaced in one step, so an interrupted run does not leave a truncated file. |

## What users can expect

- The tool acts with the user's own permissions (R5). Installers call `sudo` only for the commands that need it, for example `sudo install` when the target is `/usr/local/bin` and not writable (`get_install_cmd` in `scripts/lib/install_strategy.sh`).
- In the Python package, API tokens are used only as request headers for `https://api.github.com/rate_limit` and `https://gitlab.com/api/v4/user` (`get_github_rate_limit`, `get_gitlab_rate_limit` in `cli_audit/collectors.py`); its release lookups send no token. The installer scripts look up GitHub releases and tags with `gh api --hostname github.com`, which sends the `gh` CLI's token to api.github.com, and fall back to an unauthenticated request (`github_api_get` in `scripts/lib/install_strategy.sh`). The CLI prints only where a token came from, never the token (R3).
- Removing duplicate installations needs an explicit `--apply`; `audit.py --reconcile` alone only reports the plan (`audit.py --help`). `make upgrade-dry-run` lists the upgrades without making them (`scripts/auto_update.sh --dry-run`).
- In the progress output of `cmd_update` in `audit.py`, installed and upstream version strings are stripped of terminal control characters before they are printed (`_sanitize`). The audit table (`cli_audit/render.py`) prints version strings as received.

## What users cannot expect

- **The tool trusts its upstream distribution channels.** It installs what the package managers and upstream release pages deliver. No installer verifies a checksum or a signature of what it downloads (for example `scripts/installers/github_release_binary.sh`), and some installers run the vendor's install script (`scripts/install_rust.sh` runs rustup's installer, `scripts/install_docker.sh` runs `get.docker.com`, `scripts/install_uv.sh` runs astral.sh's installer). A compromised upstream release is installed like a genuine one.
- **The tool trusts its own catalog and configuration.** Catalog entries (`catalog/*.json`) define the version commands, download URLs and install methods, and some of them are shell commands (`version_command`, run by `get_version_line` in `cli_audit/detection.py` and by `scripts/lib/catalog_command.sh`). Configuration files set the preferred install method, target version and auto-update per tool; they are read from `.cli-audit.yml` in the current directory, `~/.config/cli-audit/config.yml` and `/etc/cli-audit/config.yml` (`CONFIG_LOCATIONS` in `cli_audit/config.py`). Run the tool from a checkout and a working directory you trust.
- **The tool does not sandbox the tools it installs.** Installed tools run with the user's permissions, and `scripts/install_docker.sh` adds the user to the `docker` group.

## Threat model

| Actor | Can do | Countered by |
| --- | --- | --- |
| Network attacker between the user and an upstream source | Read or change unencrypted traffic | R2 |
| Compromised upstream source | Serve a manipulated version string or artefact | R1 for version data in the Python package; artefacts are trusted (see "What users cannot expect") |
| A malicious installed program | Print arbitrary text when its version is queried | R1 |
| Contributor submitting a change | Change catalog entries, scripts or code | Review (`.github/CODEOWNERS`) and the CI checks in [CONTRIBUTING.md](../CONTRIBUTING.md#security-checks-on-pull-requests) |

Out of scope: an attacker who already controls the user's account, the user's configuration files or the repository checkout.

## Trust boundaries

1. **Network → tool.** Responses from the upstream sources are untrusted input. The Python package parses them with `json.loads` or a regular expression and reduces them to version strings (`cli_audit/collectors.py`); versions are compared with `packaging.version` (`cli_audit/upgrade.py`).
2. **Installed programs → tool.** The output of `<tool> --version` is untrusted input. It is matched against version patterns (`VERSION_RE` in `cli_audit/detection.py`) and not passed to a shell.
3. **Tool → system.** Install, upgrade and uninstall steps cross from the tool into the system through the scripts in `scripts/`, package managers and `sudo`.
4. **Repository → tool.** The catalog and the scripts are part of the reviewed repository and are trusted, like the program code.

## Secure design principles applied

- **Least privilege:** the tool runs as the invoking user; `sudo` is used per command, not for the whole run (R5).
- **No shell for data:** the Python package runs commands as argument lists without a shell, for example `["which", "-a", ...]` in `cli_audit/detection.py`, `["apt-cache", "policy", ...]` in `cli_audit/upgrade.py` and the uninstall commands in `cli_audit/reconcile.py`. The single use of `shell=True` runs a `version_command` from the committed catalog, with the reason in a comment (`get_version_line` in `cli_audit/detection.py`).
- **Safe parsing:** YAML configuration is read with `yaml.safe_load` (`cli_audit/config.py`); network responses and catalog files with `json.load`/`json.loads`.
- **Bounded waiting:** every HTTP request in the Python package has a timeout (`http_get` and the direct `urlopen` calls in `cli_audit/collectors.py`, `cli_audit/upgrade.py`), and version probes have `TIMEOUT_SECONDS` (`cli_audit/detection.py`).
- **Graceful degradation:** when endoflife.date cannot be reached, the last cached answer is used (`_load_endoflife_cache` in `cli_audit/collectors.py`).
- **Atomic writes:** the snapshot, the local state, the upstream version cache and the endoflife.date cache are written to a temporary file and then moved into place (`write_snapshot` in `cli_audit/snapshot.py`, `write_local_state` in `cli_audit/local_state.py`, `write_upstream_cache` in `cli_audit/upstream_cache.py`, `_save_endoflife_cache` in `cli_audit/collectors.py`).

## Countermeasures against common weaknesses

| Weakness | Countermeasure | Where |
| --- | --- | --- |
| CWE-78 OS command injection | Argument lists without a shell; `shell=True` only for catalog commands | `cli_audit/detection.py`, `cli_audit/upgrade.py`, `cli_audit/reconcile.py` |
| CWE-22 Path traversal in tool names | The installers reject tool names containing `/` or `..`; `install_tool.sh` also requires a catalog entry for the name | `scripts/install_tool.sh`, `scripts/installers/github_release_binary.sh` |
| CWE-150 Terminal escape injection | Control characters are stripped from version strings in the progress output of `cmd_update`; the audit table prints them as received | `audit.py` (`_sanitize`) |
| CWE-502 Deserialisation of untrusted data | `yaml.safe_load`; JSON only | `cli_audit/config.py`, `cli_audit/collectors.py` |
| CWE-319 Cleartext transmission | `https://` URLs; the release-binary installer restricts `curl` to HTTPS, including redirects (`--proto '=https' --proto-redir '=https'`) | `cli_audit/collectors.py`, `scripts/installers/github_release_binary.sh` |
| CWE-400 Uncontrolled resource consumption | Timeouts on the Python package's network requests and on version probes | `cli_audit/collectors.py`, `cli_audit/detection.py` |
| CWE-798 Hard-coded credentials | No credentials in the repository; Betterleaks scans every pull request | `.github/workflows/ci.yml` |
| Vulnerable dependencies (OWASP A06) | Two runtime dependencies; dependency review and pip-audit on pull requests | `pyproject.toml`, `.github/workflows/dependency-review.yml`, `.github/workflows/ci.yml` |

## Verification

- Tests: `uv run pytest` runs the unit and integration tests, including tests of the installer scripts (see [CONTRIBUTING.md](../CONTRIBUTING.md#tests)).
- Static analysis: flake8, mypy and bandit on every pull request, with each skipped bandit rule justified in `[tool.bandit]` in `pyproject.toml`; CodeQL default setup for Python and GitHub Actions.
- Review: `.github/CODEOWNERS` assigns reviewers for the code, scripts and workflows.
