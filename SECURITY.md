# Security Policy

## Reporting a Vulnerability

Please **do not** open a public issue for security-relevant findings.

Use one of the following instead:

- **Preferred:** [Privately report a vulnerability](https://github.com/netresearch/coding_agent_cli_toolset/security/advisories/new) via GitHub.
- Or email `security@netresearch.de` with details and steps to reproduce.

You should receive an acknowledgement within 3 working days. We will confirm the
issue, agree on disclosure timelines with you, and publish a fix + GitHub
Security Advisory once the fix is available.

## Scope

In scope: code in this repository, published releases of `cli-audit`, the
installation / audit / upgrade scripts under `scripts/`, and anything that
would let an attacker execute code on or exfiltrate data from a machine that
runs `make upgrade` / `audit.py` against trusted upstream sources.

Out of scope: vulnerabilities in third-party tools installed via the `install_*`
scripts (report those upstream), bugs that are only reachable by an attacker
with shell-level access to the machine running this toolkit.

## Supported Versions

Security fixes target the latest tagged release on the `main` branch. Older
tags do not receive backports.
