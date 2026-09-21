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
    [
        ("share/uv/tools/fakeuvtool", "uv"),
        ("share/pipx/venvs/fakeuvtool", "pipx"),
        ("relocated/fakeuvtool", "uv"),
        ("linked/fakeuvtool", "uv"),  # UV_TOOL_DIR names a symlink to the real dir
    ],
)
def test_reconcile_keeps_tool_manager_installation(tmp_path, monkeypatch, tool_env, manager):
    # ~/.local/bin/<tool> -> <manager dir>/<tool>/bin/<tool>; the tool dir carries
    # a pyvenv.cfg but the tool is installed, not an environment
    from cli_audit.reconcile import _check_path_ordering, clear_detection_cache, detect_installations

    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "relocated"))
    if tool_env.startswith("linked/"):
        (tmp_path / "real-tools").mkdir()
        (tmp_path / "linked").symlink_to(tmp_path / "real-tools")
        tool_env = tool_env.replace("linked/", "real-tools/")
        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "linked"))
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


@pytest.mark.parametrize(
    "layout, method, euid, expected",
    [
        ("uv/tools/gam7/bin/gam", "uv", 1000, ["uv", "tool", "uninstall", "gam7"]),
        ("pipx/venvs/httpie/bin/http", "pipx", 1000, ["pipx", "uninstall", "httpie"]),
        ("global-pipx/venvs/httpie/bin/http", "pipx", 0, ["pipx", "uninstall", "--global", "httpie"]),
    ],
)
def test_uninstall_names_the_package_and_scope(tmp_path, monkeypatch, layout, method, euid, expected):
    # catalog gam installs the gam7 package; a global pipx install needs --global
    from unittest.mock import MagicMock, patch

    from cli_audit.reconcile import Installation, _uninstall_installation

    monkeypatch.setenv("PIPX_GLOBAL_HOME", str(tmp_path / "global-pipx"))
    monkeypatch.setattr(os, "geteuid", lambda: euid, raising=False)
    inst = Installation(tool=layout.split("/")[-1], version="1", method=method, path=str(tmp_path / layout), active=False)
    with patch("cli_audit.reconcile.subprocess.run", return_value=MagicMock(returncode=0)) as run:
        assert _uninstall_installation(inst, False) == (True, None)
    assert run.call_args[0][0] == expected


def test_global_pipx_removal_is_manual_for_a_normal_user(tmp_path, monkeypatch):
    # /opt/pipx is root-owned and this tool never runs sudo: report, do not run
    from unittest.mock import patch

    from cli_audit.reconcile import Installation, _is_manual_removal_error, _uninstall_installation

    monkeypatch.setenv("PIPX_GLOBAL_HOME", str(tmp_path / "global-pipx"))
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    path = tmp_path / "global-pipx" / "venvs" / "httpie" / "bin" / "http"
    inst = Installation(tool="httpie", version="1", method="pipx", path=str(path), active=False)
    with patch("cli_audit.reconcile.subprocess.run") as run:
        ok, message = _uninstall_installation(inst, False)
    assert not ok and not run.called
    assert "sudo pipx uninstall --global httpie" in message
    assert _is_manual_removal_error(message)


def test_reinstall_hint_names_package_crate_and_scope(tmp_path, monkeypatch):
    from cli_audit.reconcile import Installation, _reinstall_hint

    monkeypatch.setenv("PIPX_GLOBAL_HOME", str(tmp_path / "global-pipx"))

    def inst(tool, method, path):
        return Installation(tool=tool, version="1", method=method, path=str(path), active=False)

    assert _reinstall_hint(inst("gam", "uv", tmp_path / "uv/tools/gam7/bin/gam")) == "uv tool install gam7"
    assert _reinstall_hint(inst("httpie", "pipx", tmp_path / "pipx/venvs/httpie/bin/http")) == "pipx install httpie"
    assert (
        _reinstall_hint(inst("httpie", "pipx", tmp_path / "global-pipx/venvs/httpie/bin/http"))
        == "sudo pipx install --global httpie"
    )
    assert _reinstall_hint(inst("fd", "cargo", "/home/u/.cargo/bin/fd")) == "cargo install fd-find"
    assert _reinstall_hint(inst("jq", "brew", "/usr/local/bin/jq")) == "brew install jq"
    assert _reinstall_hint(inst("byobu", "apt", "/usr/bin/byobu")) == "sudo apt install byobu"


def test_tool_manager_needs_package_bin_layout(tmp_path, monkeypatch):
    from cli_audit.detection import tool_manager_of

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PIPX_HOME", "~/pipx-home")  # literal ~, as a systemd unit or .env passes it
    assert tool_manager_of(str(tmp_path / "share/uv/tools/black/bin")) == "uv"
    assert tool_manager_of(str(tmp_path / "pipx-home/venvs/httpie/bin")) == "pipx"
    # not <root>/<package>/bin
    assert tool_manager_of(str(tmp_path / "share/uv/tools/bin")) == ""
    assert tool_manager_of(str(tmp_path / "share/uv/tools/black/lib")) == ""


def test_tool_bin_dir_directly_on_path_is_kept(tmp_path, monkeypatch):
    from cli_audit.reconcile import clear_detection_cache, detect_installations

    tool_bin = _make_venv(tmp_path / "share" / "uv" / "tools" / "fakedirect")
    real = _make_bin(tool_bin, "fakedirect", "1.0.0")
    monkeypatch.setenv("PATH", str(tool_bin))
    clear_detection_cache()

    assert [(i.path, i.active) for i in detect_installations("fakedirect", ["fakedirect"])] == [(str(real), True)]
    # the audit must agree: the tool is installed
    assert find_paths("fakedirect") == [str(real)]


def test_symlinked_relocated_tool_dir_on_path_is_kept(tmp_path, monkeypatch):
    from cli_audit.reconcile import clear_detection_cache, detect_installations

    (tmp_path / "real-tools").mkdir()
    (tmp_path / "linked").symlink_to(tmp_path / "real-tools")
    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "linked"))
    real = _make_bin(_make_venv(tmp_path / "real-tools" / "fakelinked"), "fakelinked", "1.0.0")
    on_path = tmp_path / "linked" / "fakelinked" / "bin"
    monkeypatch.setenv("PATH", str(on_path))
    clear_detection_cache()

    assert [i.path for i in detect_installations("fakelinked", ["fakelinked"])] == [str(real)]
    assert find_paths("fakelinked") == [str(on_path / "fakelinked")]


def test_malformed_available_method_keeps_other_catalog_data(monkeypatch):
    from cli_audit import reconcile

    class Entry:
        _raw_data = {"version_flag": "--ver", "available_methods": ["cargo", {"method": "cargo", "config": {"crate": "c"}}]}

        def to_tool(self):
            class T:
                candidates = ("x",)

            return T()

    class Catalog:
        def get(self, name):
            return Entry()

        def all_tools(self):
            return [1]

    monkeypatch.setattr(reconcile, "_catalog_instance", Catalog())
    monkeypatch.setattr(reconcile, "_catalog_cache", {})
    meta = reconcile._catalog_meta("x")
    assert meta["version_flag"] == "--ver"
    assert meta["cargo_crate"] == "c"
