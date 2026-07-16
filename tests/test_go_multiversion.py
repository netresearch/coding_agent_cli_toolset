"""Tests for multi-version go installs (GO_VERSION=1.26 install_go.sh).

After `go install golang.org/dl/go1.26.5@latest`, the script verified the
wrapper via PATH (`have go1.26.5`) — but go installs into GOBIN
(default GOPATH/bin), which may be off PATH. The SDK download and the
go1.26 cycle symlink were then silently skipped, before/after reported
`<none>`, and every auto-update run left another orphaned goX.Y.Z wrapper.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason="Shell script tests require POSIX shell"
)

SCRIPT = Path(__file__).parent.parent / "scripts" / "install_go.sh"

# Template for the goX.Y.Z wrapper the `go` stub "installs" into GOPATH/bin
WRAPPER_TEMPLATE = """#!/usr/bin/env bash
# real golang.org/dl wrappers report their own version even when invoked
# through the cycle symlink (go1.26 -> go1.26.5)
me="$(basename "$(readlink -f "$0")")"
echo "$me $*" >> "$GO_STUB_LOG"
case "$1" in
  download) exit 0 ;;
  version) echo "go version $me linux/amd64" ;;
esac
"""

GO_STUB = """#!/usr/bin/env bash
echo "go $*" >> "$GO_STUB_LOG"
case "$1" in
  env)
    case "$2" in
      GOBIN) echo "" ;;
      GOPATH) echo "$FAKE_GOPATH" ;;
    esac
    ;;
  install)
    pkg="${2#golang.org/dl/}"
    pkg="${pkg%@latest}"
    mkdir -p "$FAKE_GOPATH/bin"
    cp "$WRAPPER_TEMPLATE_PATH" "$FAKE_GOPATH/bin/$pkg"
    chmod +x "$FAKE_GOPATH/bin/$pkg"
    ;;
  version)
    echo "go version go1.26.1 linux/amd64"
    ;;
esac
exit 0
"""


@skip_on_windows
class TestGoMultiVersionInstall:
    def _setup(self, tmp_path: Path) -> tuple[dict, Path, Path]:
        stub_dir = tmp_path / "stubs"
        stub_dir.mkdir()
        gopath = tmp_path / "gopath"
        (gopath / "bin").mkdir(parents=True)
        home = tmp_path / "home"
        home.mkdir()
        log = tmp_path / "stub.log"
        log.touch()

        template = tmp_path / "wrapper.template"
        template.write_text(WRAPPER_TEMPLATE)

        for name, body in (
            ("go", GO_STUB),
            ("curl", '#!/usr/bin/env bash\necho \'[{"version":"go1.26.5"}]\'\n'),
            ("python3", "#!/usr/bin/env bash\nexit 0\n"),
        ):
            stub = stub_dir / name
            stub.write_text(body)
            stub.chmod(0o755)

        env = {
            "HOME": str(home),
            # GOPATH/bin deliberately NOT on PATH — the bug's trigger
            "PATH": f"{stub_dir}:/usr/bin:/bin",
            "GO_VERSION": "1.26",
            "FAKE_GOPATH": str(gopath),
            "GO_STUB_LOG": str(log),
            "WRAPPER_TEMPLATE_PATH": str(template),
        }
        return env, gopath, log

    def _run(self, env: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), "install"],
            capture_output=True, text=True, timeout=60, env=env,
        )

    def test_sdk_download_and_symlink_despite_gobin_off_path(self, tmp_path):
        env, gopath, log = self._setup(tmp_path)
        result = self._run(env)
        assert result.returncode == 0, result.stderr

        assert "go1.26.5 download" in log.read_text(), (
            "SDK download must run even when GOPATH/bin is off PATH"
        )
        cycle_link = gopath / "bin" / "go1.26"
        assert cycle_link.is_symlink(), "go1.26 cycle symlink must be created"
        assert os.readlink(cycle_link) == "go1.26.5"

    def test_before_after_report_not_none(self, tmp_path):
        env, _, _ = self._setup(tmp_path)
        result = self._run(env)
        out = result.stdout + result.stderr
        # "before: <none>" is correct on a fresh install — the bug was the
        # after-probe returning <none> because GOPATH/bin is off PATH
        assert "[go@1.26] after:  go version go1.26.5" in out, (
            f"after-version must probe GOPATH/bin, got: {out}"
        )

    def test_superseded_wrappers_of_same_cycle_are_removed(self, tmp_path):
        env, gopath, _ = self._setup(tmp_path)
        # Orphans from earlier runs (the wrapper zoo)
        for old in ("go1.26.0", "go1.26.2"):
            stale = gopath / "bin" / old
            stale.write_text("#!/bin/sh\n")
            stale.chmod(0o755)
            (Path(env["HOME"]) / "sdk" / old).mkdir(parents=True)
        # A different cycle must be untouched
        other = gopath / "bin" / "go1.25.11"
        other.write_text("#!/bin/sh\n")
        other.chmod(0o755)

        result = self._run(env)
        assert result.returncode == 0, result.stderr

        assert not (gopath / "bin" / "go1.26.0").exists()
        assert not (gopath / "bin" / "go1.26.2").exists()
        assert not (Path(env["HOME"]) / "sdk" / "go1.26.0").exists()
        assert (gopath / "bin" / "go1.26.5").exists()
        assert (gopath / "bin" / "go1.25.11").exists(), (
            "other cycles must not be touched"
        )
