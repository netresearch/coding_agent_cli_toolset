"""Regression tests for upgrades that `make upgrade` reported as not taking effect.

- node@26: nvm installed v26.10.0 next to v26.9.0, and detection kept 26.9.0
  because it compared the directory names as strings.
- bw: the upstream version came from the newest bitwarden/clients release,
  which is the browser extension (browser-v2026.9.1), not the npm CLI.
"""

from __future__ import annotations

import os
from pathlib import Path

from cli_audit.catalog import ToolCatalog
from cli_audit.detection import detect_multi_versions


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


class TestBitwardenUpstreamIsNpm:
    def test_bw_version_comes_from_the_npm_package(self):
        tool = ToolCatalog().get("bw").to_tool()
        assert tool.source_kind == "npm"
        assert tool.source_args == ("@bitwarden/cli",)
