# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""Regression tests for upgrades that `make upgrade` reported as not taking effect.

- node@26: nvm installed v26.10.0 next to v26.9.0, and detection kept 26.9.0
  because it compared the directory names as strings.
- bw: the upstream version came from the newest bitwarden/clients release,
  which is the browser extension (browser-v2026.9.1), not the npm CLI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from cli_audit.catalog import ToolCatalog
from cli_audit.detection import detect_multi_versions

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _fake_nvm(tmp_path, versions):
    for v in versions:
        bin_dir = tmp_path / f"v{v}" / "bin"
        bin_dir.mkdir(parents=True)
        node = bin_dir / "node"
        node.write_text("#!/bin/sh\n")
        os.chmod(node, 0o700)
    return str(tmp_path)


class TestMultiVersionPicksNumericallyHighest:
    def test_two_digit_minor_beats_one_digit_minor(self, tmp_path):
        base = _fake_nvm(tmp_path, ["26.9.0", "26.10.0", "26.8.1"])
        rows = detect_multi_versions(
            "node",
            {"version_manager_dir": base, "version_prefix": "v", "binary_name": "node"},
            [{"cycle": "26", "latest": "26.10.0", "status": "active"}],
        )
        assert rows[0]["installed"] == "26.10.0"
        assert Path(rows[0]["path"]).parts[-3:] == ("v26.10.0", "bin", "node")

    def test_release_beats_its_prerelease(self, tmp_path):
        base = _fake_nvm(tmp_path, ["26.0.0-rc.1", "26.0.0"])
        rows = detect_multi_versions(
            "node",
            {"version_manager_dir": base, "version_prefix": "v", "binary_name": "node"},
            [{"cycle": "26", "latest": "26.0.0", "status": "active"}],
        )
        assert rows[0]["installed"] == "26.0.0"


class TestMultiVersionCycleIsValidated:
    """A cycle read back from the snapshot file must not steer the binary path."""

    def _fake_go(self, tmp_path, rel):
        go = tmp_path / rel / "bin" / "go"
        go.parent.mkdir(parents=True)
        go.write_text("#!/bin/sh\n")
        os.chmod(go, 0o700)
        return go

    @skip_on_windows
    def test_release_cycle_is_found(self, tmp_path):
        go = self._fake_go(tmp_path, "go1.25")
        rows = detect_multi_versions("demo", {"candidates": [f"{tmp_path}/go{{cycle}}/bin/go"]}, [{"cycle": "1.25"}])
        assert rows[0]["path"] == str(go)

    def test_cycle_with_path_traversal_is_skipped(self, tmp_path):
        (tmp_path / "go").mkdir()
        self._fake_go(tmp_path, "planted")
        rows = detect_multi_versions("demo", {"candidates": [f"{tmp_path}/go{{cycle}}/bin/go"]}, [{"cycle": "/../planted"}])
        assert rows == []


class TestBitwardenUpstreamIsNpm:
    def test_bw_version_comes_from_the_npm_package(self):
        tool = ToolCatalog().get("bw").to_tool()
        assert tool.source_kind == "npm"
        assert tool.source_args == ("@bitwarden/cli",)
