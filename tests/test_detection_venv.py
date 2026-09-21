"""Tests for virtualenv exclusion in audit detection.

An always-activated ~/.venv put ~/.venv/bin first on PATH. The audit reported
~/.venv/bin/black (25.11.0, "via manual") as the installation, so every
`uv tool upgrade black` of the real ~/.local/bin/black (26.5.1) looked like a
no-op and the tool stayed "outdated" run after run. Environments are not
installations: reconcile.py and capability.sh already skip them, and the
audit detection must too.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from cli_audit.bulk import get_missing_tools
from cli_audit.detection import audit_tool_installation, find_paths
from cli_audit.installer import validate_installation

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Uses Unix-style paths and PATH separator (:)",
)


# The deep search runs `which -a`; without its dir on PATH the subprocess
# fails, the error is swallowed and only the fast path would be tested
WHICH_DIR = os.path.dirname(shutil.which("which") or "/usr/bin/which")


def _make_bin(bin_dir: Path, name: str, version: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / name
    binary.write_text(f"#!/bin/sh\necho '{name} {version}'\n")
    binary.chmod(0o755)
    return binary


def _make_venv(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyvenv.cfg").write_text("home = /usr/bin\n")
    return root / "bin"


def test_activated_venv_does_not_shadow_the_installation(tmp_path, monkeypatch):
    venv_bin = _make_venv(tmp_path / "home" / ".venv")
    _make_bin(venv_bin, "fakeblack", "25.11.0")
    local_bin = tmp_path / "home" / ".local" / "bin"
    real = _make_bin(local_bin, "fakeblack", "26.5.1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), str(local_bin)]))

    version, _line, path, _method = audit_tool_installation("fakeblack", ("fakeblack",))

    assert (version, path) == ("26.5.1", str(real))


def test_deep_search_skips_venv_bin(tmp_path, monkeypatch):
    venv_bin = _make_venv(tmp_path / "env-with-any-name")
    _make_bin(venv_bin, "faketool", "1.0.0")
    other_bin = tmp_path / "other" / "bin"
    real = _make_bin(other_bin, "faketool", "2.0.0")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), str(other_bin), WHICH_DIR]))

    assert find_paths("faketool", deep=True) == [str(real)]


def test_tool_only_in_venv_is_not_installed(tmp_path, monkeypatch):
    venv_bin = _make_venv(tmp_path / ".venv")
    _make_bin(venv_bin, "fakeonlyvenv", "7.3.0")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), WHICH_DIR]))

    assert find_paths("fakeonlyvenv", deep=True) == []


def test_version_command_skips_the_venv_copy(tmp_path, monkeypatch):
    # Catalog version_command names the tool ("black --version"); it must not
    # resolve to the activated venv's copy either
    venv_bin = _make_venv(tmp_path / ".venv")
    _make_bin(venv_bin, "fakeblack2", "25.11.0")
    local_bin = tmp_path / ".local" / "bin"
    real = _make_bin(local_bin, "fakeblack2", "26.5.1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), str(local_bin)]))

    version, _line, path, _method = audit_tool_installation(
        "fakeblack2", ("fakeblack2",), version_command="fakeblack2 --version"
    )

    assert (version, path) == ("26.5.1", str(real))


def test_bin_pattern_needs_a_directory_boundary(tmp_path, monkeypatch):
    # "/venv/bin" must not match /opt/venv/bin-extra: that is no environment
    extra_bin = tmp_path / "opt" / "venv" / "bin-extra"
    real = _make_bin(extra_bin, "faketool3", "3.0.0")
    monkeypatch.setenv("PATH", str(extra_bin))

    assert find_paths("faketool3") == [str(real)]


def test_missing_tool_check_ignores_venv_copy(tmp_path, monkeypatch):
    # bulk install must agree with the audit: a venv-only tool is missing
    venv_bin = _make_venv(tmp_path / ".venv")
    _make_bin(venv_bin, "fakeonlyvenv2", "7.3.0")
    monkeypatch.setenv("PATH", str(venv_bin))

    assert get_missing_tools(["fakeonlyvenv2"]) == ["fakeonlyvenv2"]


def test_install_validation_checks_the_installed_copy(tmp_path, monkeypatch):
    venv_bin = _make_venv(tmp_path / ".venv")
    _make_bin(venv_bin, "fakeblack3", "25.11.0")
    local_bin = tmp_path / ".local" / "bin"
    real = _make_bin(local_bin, "fakeblack3", "26.5.1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), str(local_bin)]))

    ok, path, version = validate_installation("fakeblack3")

    assert (ok, path) == (True, str(real))
    assert "26.5.1" in (version or "")


def test_trailing_slash_venv_bin_is_skipped(tmp_path, monkeypatch):
    # export PATH=~/proj-env/bin/:$PATH
    venv_bin = _make_venv(tmp_path / "proj-env")
    _make_bin(venv_bin, "faketool4", "1.0.0")
    other_bin = tmp_path / "other" / "bin"
    real = _make_bin(other_bin, "faketool4", "2.0.0")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin) + "/", str(other_bin)]))

    assert find_paths("faketool4") == [str(real)]


@pytest.mark.parametrize(
    "tool_env, manager",
    [("share/uv/tools/fakeuvtool", "uv"), ("share/pipx/venvs/fakeuvtool", "pipx"), ("relocated/fakeuvtool", "uv")],
)
def test_reconcile_keeps_tool_manager_installation(tmp_path, monkeypatch, tool_env, manager):
    # ~/.local/bin/<tool> -> <manager dir>/<tool>/bin/<tool>; the tool dir carries
    # a pyvenv.cfg but the tool is installed, not an environment
    from cli_audit.reconcile import _check_path_ordering, clear_detection_cache, detect_installations

    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "relocated"))
    real = _make_bin(_make_venv(tmp_path / tool_env), "fakeuvtool", "26.5.1")
    local_bin = tmp_path / "local" / "bin"
    local_bin.mkdir(parents=True)
    (local_bin / "fakeuvtool").symlink_to(real)
    venv_bin = _make_venv(tmp_path / ".venv")
    _make_bin(venv_bin, "fakeuvtool", "25.11.0")
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv_bin), str(local_bin)]))
    clear_detection_cache()

    installs = detect_installations("fakeuvtool", ["fakeuvtool"])

    assert [(i.path, i.method, i.active) for i in installs] == [(str(real), manager, True)]
    # PATH advice names the dir on PATH, not the manager's internal bin dir
    inactive = installs[0].__class__(**{**installs[0].__dict__, "active": False})
    other = installs[0].__class__(**{**installs[0].__dict__, "path": "/usr/bin/fakeuvtool"})
    assert f"Ensure {local_bin} appears first" in _check_path_ordering(inactive, other, False)[0]
