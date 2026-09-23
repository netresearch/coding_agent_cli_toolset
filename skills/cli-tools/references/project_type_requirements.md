# Project Type Requirements

`scripts/detect_project_type.sh json <dir>` detects the types below and lists
their **required** and **recommended** tools by catalog name, ready for
`install_tool.sh`. `scripts/check_environment.sh project <dir>` checks the
required ones. The two tables must agree; `tests/test_claude_plugin.py`
checks the first against the script.

## Detected types

| Type | Detected by | Required | Recommended |
|------|-------------|----------|-------------|
| python | `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | `python`, `uv` | `ruff`, `black` |
| node | `package.json` | `node`, `npm` | `eslint`, `prettier` |
| rust | `Cargo.toml` | `rust` | |
| go | `go.mod` | `go` | `golangci-lint` |
| ruby | `Gemfile`, `.ruby-version` | `ruby` | |
| php | `composer.json`, `composer.lock`, `*.php` | `php`, `composer` | |
| docker | `Dockerfile`, `docker-compose.y(a)ml`, `compose.y(a)ml` | `docker`, `compose` | `dive`, `trivy` |
| terraform | `*.tf`, `terraform/` | `terraform` | `tfsec`, `trivy` |
| kubernetes | `k8s/`, `*/deployment.yaml` | `kubectl` | |
| ansible | `ansible.cfg`, `playbooks/` | `ansible-core` | |
| shell | `Makefile`, `*.sh` | | `shellcheck`, `shfmt` |

## Tools that belong to the project, not the machine

These are pinned per project and installed by its own package manager, so they
have no catalog entry. Install them there, not globally:

| Type | Tools | Install |
|------|-------|---------|
| python | `mypy`, `pytest` | `uv add --dev <tool>` |
| node | `typescript` | `npm install --save-dev typescript` |
| php | `phpstan`, `phpcs`, `phpunit`, `php-cs-fixer` | `composer require --dev <package>` |
| ruby | `bundler`, `rubocop` | `gem install bundler`, then the Gemfile |
| rust | `cargo-audit`, `cargo-watch` | `cargo install <crate>` |

## Always useful

`git`, `gh`, `jq`, `yq`, `ripgrep`, `fd`, `fzf`, `bat`, `delta` — all
cataloged; `check_environment.sh audit` reports the core ones.

## Several types at once

A repository is often several types (python + shell, node + docker). The JSON
output merges and de-duplicates the tool lists of every detected type.
