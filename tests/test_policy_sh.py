# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
"""scripts/lib/policy.sh — is_sudo_allowed reads allow_sudo from the user config.

An explicit ``"allow_sudo": false`` has to refuse sudo, with and without jq.
A missing key or a missing file keeps the default, which allows sudo.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
POLICY_SH = PROJECT_ROOT / "scripts" / "lib" / "policy.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def _sudo_allowed(tmp_path: Path, config: dict | None, path: str) -> bool:
    cfg = tmp_path / "config.json"
    if config is not None:
        cfg.write_text(json.dumps(config))
    proc = subprocess.run(
        ["bash", "-c", f'source "{POLICY_SH}"; is_sudo_allowed'],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": path, "AI_CLI_PREP_CONFIG": str(cfg)},
        timeout=60,
    )
    return proc.returncode == 0


def _path_without_jq(tmp_path: Path) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in ("bash", "grep", "dirname", "uname", "sed", "awk", "cat"):
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    return str(bindir)


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"allow_sudo": False}, False),
        ({"allow_sudo": True}, True),
        ({}, True),
        (None, True),
    ],
)
def test_allow_sudo_with_jq(tmp_path, config, expected):
    assert _sudo_allowed(tmp_path, config, os.environ["PATH"]) is expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"allow_sudo": False}, False),
        ({"allow_sudo": True}, True),
        ({}, True),
    ],
)
def test_allow_sudo_without_jq(tmp_path, config, expected):
    path = _path_without_jq(tmp_path)
    assert shutil.which("jq", path=path) is None
    assert _sudo_allowed(tmp_path, config, path) is expected
