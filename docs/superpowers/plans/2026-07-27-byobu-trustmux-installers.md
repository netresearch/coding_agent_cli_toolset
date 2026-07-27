# Byobu and Trustmux Upstream Installers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audited, user-local installations of the latest stable Byobu and Trustmux releases without using distribution packages.

**Architecture:** Byobu uses a dedicated Bash installer because upstream publishes source tags rather than a standalone binary; it selects only numeric stable tags, builds the tagged archive, and installs under `~/.local`. Trustmux uses the existing generic `uv_tool` installer and its official PyPI package. Both catalog entries feed the existing GitHub/PyPI collectors and snapshot model.

**Tech Stack:** Bash, GitHub REST API/source archives, Autoconf/Automake/Make, JSON catalog metadata, uv/PyPI, pytest.

---

## Task 1: Specify catalog and installer behavior with failing tests

**Files:**
- Modify: `tests/test_catalog_and_collectors.py`
- Test: `tests/test_catalog_and_collectors.py`

- [ ] Add `TestByobuCatalog` assertions for `catalog/byobu.json`, `name == "byobu"`, `install_method == "dedicated_script"`, `script == "install_byobu.sh"`, `github_repo == "dustinkirkland/byobu"`, `binary_name == "byobu"`, and `requires == ["tmux"]`.
- [ ] Add `TestByobuInstallScript` assertions that `scripts/install_byobu.sh` exists, is executable, filters tags with the stable numeric expression `^[0-9]+([.][0-9]+)+$`, uses the GitHub tag archive URL, configures `--prefix="$INSTALL_PREFIX"`, supports uninstall, and verifies `$INSTALL_PREFIX/bin/byobu`.
- [ ] Add `TestTrustmuxCatalog` assertions for `catalog/trustmux.json`, `install_method == "uv_tool"`, `package_name == "trustmux"`, `binary_name == "trustmux"`, `source_kind == "pypi"`, and `requires == ["tmux"]`.
- [ ] Run `UV_CACHE_DIR=/tmp/cli-toolset-uv-cache /home/sme/.local/bin/uv run pytest tests/test_catalog_and_collectors.py -k 'Byobu or Trustmux' -q` and confirm failure because the new files do not exist.

## Task 2: Implement the Byobu source installer and both catalog entries

**Files:**
- Create: `scripts/install_byobu.sh`
- Create: `catalog/byobu.json`
- Create: `catalog/trustmux.json`
- Modify: `catalog/README.md`

- [ ] Create `catalog/byobu.json` with category `general`, dedicated installer metadata, homepage `https://byobu.org/`, GitHub repository `dustinkirkland/byobu`, `byobu --version` detection, tmux dependency, and notes that source installation avoids stale apt packages.
- [ ] Create `catalog/trustmux.json` with category `security`, `uv_tool`, official homepage `https://trustmux.dev/`, PyPI package/binary `trustmux`, `trustmux --version` detection, tmux dependency, and notes that PyPI avoids stale distro packages.
- [ ] Create strict-mode `scripts/install_byobu.sh` with `install`, `update`, and `uninstall` dispatch.
- [ ] Implement latest-version lookup using the GitHub tags API, accepting only numeric stable tags and sorting them with `sort -V`; accept an explicit version as the second script argument for reproducible installs.
- [ ] Download `https://github.com/dustinkirkland/byobu/archive/refs/tags/${version}.tar.gz` with HTTPS failure handling, retries, timeouts, temporary-directory cleanup, and retained build-log tail on failure.
- [ ] Check required build commands, run `./autogen.sh`, `./configure --prefix="$INSTALL_PREFIX"`, `make`, and `make install`, then verify the direct path `$INSTALL_PREFIX/bin/byobu` reports the requested version.
- [ ] Make `scripts/install_byobu.sh` executable and update both catalog count references from 101 to 103.
- [ ] Run the focused tests and confirm they pass.
- [ ] Run `bash -n scripts/install_byobu.sh` and `shellcheck -x scripts/install_byobu.sh`.

## Task 3: Record upstream versions and perform real user-local installs

**Files:**
- Modify: `upstream_versions.json`
- Runtime outputs: `local_state.json` and audit snapshot (gitignored)
- Install destinations: `~/.local/bin/byobu` and the uv tool directory exposing `~/.local/bin/trustmux`

- [ ] Update the committed baseline with `UV_CACHE_DIR=/tmp/cli-toolset-uv-cache /home/sme/.local/bin/uv run python audit.py --update-baseline byobu` and the equivalent command for `trustmux`.
- [ ] Confirm baseline versions are Byobu `7.15` from the GitHub tag collector and Trustmux `7.15` from PyPI, preserving unrelated baseline metadata.
- [ ] Install Byobu with `FORCE_INSTALL=1 ./scripts/install_byobu.sh update 7.15`.
- [ ] Install Trustmux with `UV_CACHE_DIR=/tmp/cli-toolset-uv-cache ./scripts/install_tool.sh trustmux update`.
- [ ] Verify `/home/sme/.local/bin/byobu --version` and `/home/sme/.local/bin/trustmux --version`.
- [ ] Refresh/merge local collection with `CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 UV_CACHE_DIR=/tmp/cli-toolset-uv-cache /home/sme/.local/bin/uv run python audit.py byobu trustmux`.
- [ ] Confirm JSON audit output reports both tools installed from user-local paths and up to date.

## Task 4: Run complete verification and commit only scoped changes

**Files:**
- Verify all changed files

- [ ] Run `UV_CACHE_DIR=/tmp/cli-toolset-uv-cache /home/sme/.local/bin/uv run pytest -q`.
- [ ] Run `UV_CACHE_DIR=/tmp/cli-toolset-uv-cache /home/sme/.local/bin/uv run python -m flake8 cli_audit tests`.
- [ ] Run `./scripts/test_smoke.sh`.
- [ ] Run `git diff --check` and inspect `git status --short`.
- [ ] Preserve unrelated modifications to `scripts/lib/bashrc.sh`, `scripts/lib/completion.sh`, and `requirements-frozen-20260722.txt`.
- [ ] Commit the tmux installer fix separately as `fix(scripts): install tmux binary without manpage`.
- [ ] Commit the catalog/installer work, including Bubblewrap, Byobu, Trustmux, tests, baseline, and catalog counts, as `feat(catalog): add sandbox and terminal tools`.
