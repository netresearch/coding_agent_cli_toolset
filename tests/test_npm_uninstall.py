# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Tests for the npm handler of remove_installation: the package name comes
from the binary's symlink into node_modules (or from a pnpm shim), not from the
tool name, and the removal acts on the prefix the binary lives in."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

# A pnpm 10 global bin, as `pnpm add -g @earendil-works/pi-coding-agent` writes
# it to $PNPM_HOME/pi (store path shortened): a shell shim, not a symlink
PNPM_PKG_DIR = "global/5/.pnpm/@earendil-works+pi-coding-agent@1.5.0_ws@8.22.2/node_modules/@earendil-works/pi-coding-agent"
PNPM_SHIM = """#!/bin/sh
basedir=$(dirname "$(echo "$0" | sed -e 's,\\\\,/,g')")
if [ -z "$NODE_PATH" ]; then
  export NODE_PATH="{home}/{pkg}/node_modules:{home}/global/5/.pnpm/node_modules"
fi
if [ -x "$basedir/node" ]; then
  exec "$basedir/node"  "$basedir/{pkg}/dist/cli.js" "$@"
else
  exec node  "$basedir/{pkg}/dist/cli.js" "$@"
fi
"""


def _write_stub(stub_dir: Path, name: str, body: str) -> Path:
    """Create an executable stub command in stub_dir."""
    stub = stub_dir / name
    stub.write_text(f"#!/usr/bin/env bash\n{body}\n")
    stub.chmod(0o755)
    return stub


def _run_removal(tmpdir: str, tool: str, path: Path) -> str:
    """Run remove_installation for an npm-classified PATH; return the npm and
    pnpm calls it made."""
    stub_dir = Path(tmpdir) / "stubs"
    stub_dir.mkdir()
    log_file = stub_dir / "calls.log"
    log_file.touch()
    _write_stub(stub_dir, "npm", f'echo "npm $*" >> "{log_file}"')
    _write_stub(stub_dir, "pnpm", f'echo "pnpm $*" >> "{log_file}"')
    # The catalog lookup needs jq, which may live outside /usr/bin:/bin
    jq = shutil.which("jq")
    if jq:
        (stub_dir / "jq").symlink_to(jq)

    result = subprocess.run(
        [
            "bash",
            "-c",
            f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
export PATH="{stub_dir}:/usr/bin:/bin"
hash -r
remove_installation "{tool}" "npm" "{tool}" "{path}"
""",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "HOME": tmpdir},
    )
    assert result.returncode == 0, result.stderr
    return log_file.read_text()


@skip_on_windows
class TestRemoveInstallationNpmPackageName:
    """The npm handler must uninstall the package that owns the binary."""

    def _remove(self, tmpdir: str, bin_target: str, tool: str, linked_pkg: str = "") -> tuple[str, Path]:
        """Link <prefix>/bin/<tool> to bin_target; return the calls and the prefix.

        linked_pkg: make node_modules/<linked_pkg> a symlink to a source
        folder, the layout of `npm link` and `npm install -g <folder>`.
        """
        prefix = Path(tmpdir) / "prefix"
        target = prefix / "lib" / bin_target
        if linked_pkg:
            pkg_dir = prefix / "lib" / "node_modules" / linked_pkg
            source = Path(tmpdir) / "src"
            (source / Path(bin_target).relative_to(Path("node_modules") / linked_pkg)).parent.mkdir(parents=True)
            pkg_dir.parent.mkdir(parents=True, exist_ok=True)
            pkg_dir.symlink_to(source)
        else:
            target.parent.mkdir(parents=True)
        target.write_text("#!/usr/bin/env node\n")
        (prefix / "bin").mkdir()
        link = prefix / "bin" / tool
        link.symlink_to(Path("..") / "lib" / bin_target)
        return _run_removal(tmpdir, tool, link), prefix

    def test_scoped_package_is_read_from_the_bin_symlink(self):
        # The layout of a real `npm install -g @earendil-works/pi-coding-agent`.
        # A bare `npm uninstall -g pi` would target the unrelated package `pi`.
        with tempfile.TemporaryDirectory() as tmpdir:
            log, prefix = self._remove(
                tmpdir,
                "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js",
                "pi",
            )
            assert log == f"npm uninstall -g --prefix {prefix} @earendil-works/pi-coding-agent\n"

    def test_unscoped_package_is_read_from_the_bin_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # `tsc` is the bin of the package `typescript`
            log, prefix = self._remove(tmpdir, "node_modules/typescript/bin/tsc", "tsc")
            assert log == f"npm uninstall -g --prefix {prefix} typescript\n"

    def test_linked_package_directory_is_not_resolved_past(self):
        # `npm link` / `npm install -g <folder>`: the package directory is a
        # symlink too, so a full resolution would leave node_modules behind
        with tempfile.TemporaryDirectory() as tmpdir:
            log, prefix = self._remove(
                tmpdir,
                "node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
                "pi",
                linked_pkg="@earendil-works/pi-coding-agent",
            )
            assert log == f"npm uninstall -g --prefix {prefix} @earendil-works/pi-coding-agent\n"

    def test_nested_scoped_dependency_names_the_owning_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log, prefix = self._remove(tmpdir, "node_modules/owner/node_modules/@d/e/bin/x", "x")
            assert log == f"npm uninstall -g --prefix {prefix} owner\n"

    def test_binary_outside_node_modules_falls_back_to_tool_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log, _ = self._remove(tmpdir, "other/sometool", "sometool")
            assert log == "npm uninstall -g sometool\n"

    def test_absolute_symlink_names_its_prefix(self):
        # The prefix is where node_modules sits, not the directory of the link
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = Path(tmpdir) / "npm-global"
            target = prefix / "lib" / "node_modules" / "typescript" / "bin" / "tsc"
            target.parent.mkdir(parents=True)
            target.write_text("#!/usr/bin/env node\n")
            link = Path(tmpdir) / "elsewhere" / "tsc"
            link.parent.mkdir()
            link.symlink_to(target)
            log = _run_removal(tmpdir, "tsc", link)
            assert log == f"npm uninstall -g --prefix {prefix} typescript\n"


@skip_on_windows
class TestRemoveInstallationPnpm:
    """pnpm global bins are shims; their packages are removed with pnpm."""

    def test_scoped_package_is_read_from_the_pnpm_shim(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pnpm_home = Path(tmpdir) / ".local" / "share" / "pnpm"
            pnpm_home.mkdir(parents=True)
            shim = pnpm_home / "pi"
            shim.write_text(PNPM_SHIM.format(home=pnpm_home, pkg=PNPM_PKG_DIR))
            shim.chmod(0o755)
            log = _run_removal(tmpdir, "pi", shim)
            assert log == "pnpm remove -g @earendil-works/pi-coding-agent\n"

    def test_unscoped_package_is_read_from_the_pnpm_shim(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shim = Path(tmpdir) / "tsc"
            shim.write_text(
                '#!/bin/sh\nexec node  "$basedir/global/5/.pnpm/typescript@7.0.2/node_modules/typescript/bin/tsc" "$@"\n'
            )
            shim.chmod(0o755)
            log = _run_removal(tmpdir, "tsc", shim)
            assert log == "pnpm remove -g typescript\n"

    @pytest.mark.skipif(shutil.which("jq") is None, reason="catalog lookup needs jq")
    def test_unparseable_binary_falls_back_to_catalog_package_name(self):
        # Neither a symlink nor a pnpm shim: the catalog's package_name names
        # the npm package; the tool name `pi` is an unrelated package
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "pi"
            binary.write_text("#!/bin/sh\nexec node /somewhere/cli.js\n")
            binary.chmod(0o755)
            log = _run_removal(tmpdir, "pi", binary)
            assert log == "npm uninstall -g @earendil-works/pi-coding-agent\n"


@skip_on_windows
class TestNpmPrefixClassification:
    """A bin in npm's global layout classifies as npm under any prefix."""

    def _classify(self, tmpdir: str, func: str, link: Path) -> str:
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/capability.sh"
export PATH="{link.parent}:/usr/bin:/bin"
hash -r
if [ "{func}" = classify_install_path ]; then
  classify_install_path "{link.name}" "{link}"
else
  detect_install_method "{link.name}" "{link.name}"
fi
""",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "HOME": tmpdir},
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def _layout(self, tmpdir: str, bin_dir: str, rel_target: str) -> Path:
        prefix = Path(tmpdir) / bin_dir
        target = prefix / "lib" / rel_target
        target.parent.mkdir(parents=True)
        target.write_text("#!/bin/sh\n")
        target.chmod(0o755)
        (prefix / "bin").mkdir()
        link = prefix / "bin" / "sometool"
        link.symlink_to(Path("..") / "lib" / rel_target)
        return link

    @pytest.mark.parametrize("func", ["classify_install_path", "detect_install_method"])
    def test_custom_prefix_is_npm(self, func):
        # e.g. `npm config set prefix ~/.npm-global`
        with tempfile.TemporaryDirectory() as tmpdir:
            link = self._layout(tmpdir, ".npm-global", "node_modules/sometool/cli.js")
            assert self._classify(tmpdir, func, link) == "npm"

    @pytest.mark.parametrize("func", ["classify_install_path", "detect_install_method"])
    def test_home_local_prefix_is_npm(self, func):
        # `npm config set prefix ~/.local`: bins land in ~/.local/bin
        with tempfile.TemporaryDirectory() as tmpdir:
            link = self._layout(tmpdir, ".local", "node_modules/sometool/cli.js")
            assert self._classify(tmpdir, func, link) == "npm"

    @pytest.mark.parametrize("func", ["classify_install_path", "detect_install_method"])
    def test_symlink_outside_node_modules_stays_unknown(self, func):
        with tempfile.TemporaryDirectory() as tmpdir:
            link = self._layout(tmpdir, ".npm-global", "other/sometool")
            assert self._classify(tmpdir, func, link) == "unknown"


@skip_on_windows
class TestReconcileToolPassesPath:
    """reconcile_tool hands the classified path to remove_installation."""

    def test_detected_path_is_passed_to_the_removal(self, tmp_path: Path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        binary = bin_dir / "sometool"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        catalog = tmp_path / "sometool.json"
        catalog.write_text('{"install_method": "auto", "binary_name": "sometool"}')
        jq = shutil.which("jq")
        if jq is None:
            pytest.skip("reconcile_tool needs jq")
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"""
set -euo pipefail
source "{SCRIPTS_DIR}/lib/reconcile.sh"
export PATH="{bin_dir}:{Path(jq).parent}:/usr/bin:/bin"
hash -r
detect_install_method() {{ echo manual; }}
resolve_best_method() {{ echo cargo; }}
get_method_config() {{ echo '{{}}'; }}
install_via_method() {{ return 0; }}
resolve_global_bin() {{ echo ""; }}
remove_installation() {{ echo "remove $*"; }}
reconcile_tool "{catalog}" reconcile || true
""",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        assert f"remove sometool manual sometool {binary}" in result.stdout, result.stderr
