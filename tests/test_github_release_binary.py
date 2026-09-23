"""scripts/installers/github_release_binary.sh — version resolution and report.

Three failure shapes, each observed in the field:

* The GitHub fallback ran `curl … | awk` inside an assignment under
  ``set -euo pipefail``. A failing curl (rate limit, network) killed the
  script at that line with no output at all, so the "Unable to resolve
  latest version" message below it was never reached.
* The only GitHub lookup was an unauthenticated redirect probe, which shared
  CI runner IPs exhaust quickly. The authenticated ``github_api_get`` helper
  (gh first, curl second) already existed and was not used here.
* The report probed whichever copy of the binary came first on PATH, so with
  more than one installation it could print the version of a different copy
  than the one just written.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
INSTALLER = PROJECT_ROOT / "scripts" / "installers" / "github_release_binary.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

NEW_VERSION = "39.9.9"
OLD_VERSION = "0.0.1"


def _write_exe(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _curl_stub(log: Path, serve_download: bool, failing_writeout: bool = False) -> str:
    """A curl that fails every lookup and optionally serves the fx download.

    It records each URL it is asked for, so a test can see which lookups ran.
    """
    download = (
        f"""    */releases/download/*)
      [ -n "$out" ] && printf '#!/usr/bin/env bash\\necho "fx {NEW_VERSION}"\\n' > "$out"
      exit 0 ;;"""
        if serve_download
        else ""
    )
    writeout = """    */releases/latest) printf '%s' "$url"; exit 22 ;;""" if failing_writeout else ""
    return f"""out=""
prev=""
url=""
for arg in "$@"; do
  [ "$prev" = "-o" ] && out="$arg"
  case "$arg" in http*) url="$arg" ;; esac
  prev="$arg"
done
echo "$url" >> "{log}"
case "$url" in
{download}
{writeout}
  *) exit 22 ;;
esac
"""


@pytest.fixture
def sandbox(tmp_path: Path):
    """HOME, PREFIX and a stub bin dir that shadows gh and curl."""
    home = tmp_path / "home"
    home.mkdir()
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    prefix = tmp_path / "prefix"
    return home, stubs, prefix, tmp_path / "curl.log"


def _run(
    home: Path, stubs: Path, prefix: Path, extra_path: str = "", extra_env: dict | None = None
) -> subprocess.CompletedProcess:
    path = os.pathsep.join(p for p in (str(stubs), extra_path, os.environ["PATH"]) if p)
    env = {
        **os.environ,
        "HOME": str(home),
        "PREFIX": str(prefix),
        "INSTALL_STRATEGY": "USER",
        "PATH": path,
        "CLI_AUDIT_MARKER_DIR": str(home / "markers"),
    }
    env.update(extra_env or {})
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    return subprocess.run(["bash", str(INSTALLER), "fx"], capture_output=True, text=True, env=env, timeout=60)


def test_unresolvable_version_reports_the_error_instead_of_dying_silently(sandbox):
    home, stubs, prefix, log = sandbox
    _write_exe(stubs / "gh", "exit 1\n")
    _write_exe(stubs / "curl", _curl_stub(log, serve_download=False))

    proc = _run(home, stubs, prefix)

    assert proc.returncode != 0
    assert "Unable to resolve latest version" in proc.stderr, (
        "the installer died before its own error message; stderr was:\n" + proc.stderr
    )


def test_latest_version_comes_from_the_authenticated_api(sandbox):
    home, stubs, prefix, log = sandbox
    _write_exe(
        stubs / "gh",
        f"""case "$*" in
  *"repos/antonmedv/fx/releases/latest"*) printf '{{"tag_name":"{NEW_VERSION}"}}' ;;
  *) exit 1 ;;
esac
""",
    )
    _write_exe(stubs / "curl", _curl_stub(log, serve_download=True))

    proc = _run(home, stubs, prefix)

    requested = log.read_text() if log.exists() else ""
    assert f"/releases/download/{NEW_VERSION}/" in requested, requested + "\n" + proc.stderr
    assert (
        "github.com/antonmedv/fx/releases/latest" not in requested
    ), "fell back to the unauthenticated redirect although gh answered"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the installer is Linux-only (OS=linux, GNU `install -T`); this case runs the install to completion",
)
def test_report_probes_the_installed_binary_not_the_first_on_path(sandbox):
    home, stubs, prefix, log = sandbox
    _write_exe(
        stubs / "gh",
        f"""case "$*" in
  *"repos/antonmedv/fx/releases/latest"*) printf '{{"tag_name":"{NEW_VERSION}"}}' ;;
  *) exit 1 ;;
esac
""",
    )
    _write_exe(stubs / "curl", _curl_stub(log, serve_download=True))
    # A second, older copy that PATH resolves first.
    other = sandbox[0].parent / "other-bin"
    _write_exe(other / "fx", f'echo "fx {OLD_VERSION}"\n')

    proc = _run(home, stubs, prefix, extra_path=str(other))

    installed = prefix / "bin" / "fx"
    assert installed.exists(), proc.stdout + proc.stderr
    assert f"[fx] after:  {NEW_VERSION}" in proc.stdout, proc.stdout + proc.stderr
    assert f"[fx] path:   {installed}" in proc.stdout, proc.stdout


def test_a_failed_redirect_probe_is_not_read_as_a_tag(sandbox):
    # curl -f still prints its -w write-out on an HTTP error: the URL ends in
    # /releases/latest, and taking its last component yielded the tag "latest".
    home, stubs, prefix, log = sandbox
    _write_exe(stubs / "gh", "exit 1\n")
    _write_exe(stubs / "curl", _curl_stub(log, serve_download=True, failing_writeout=True))

    proc = _run(home, stubs, prefix)

    requested = log.read_text() if log.exists() else ""
    assert "/releases/download/" not in requested, "downloaded a release named after a failed lookup:\n" + requested
    assert "Unable to resolve latest version" in proc.stderr, proc.stderr


def test_the_gh_lookup_targets_github_com_whatever_gh_host_says(sandbox):
    # gh follows GH_HOST, or the host of the repository it runs in; the
    # catalog repositories and the helper's own curl fallback are github.com.
    home, stubs, prefix, log = sandbox
    _write_exe(
        stubs / "gh",
        f"""case "$*" in
  *"--hostname github.com"*"repos/antonmedv/fx/releases/latest"*) printf '{{"tag_name":"{NEW_VERSION}"}}' ;;
  *) exit 1 ;;
esac
""",
    )
    _write_exe(stubs / "curl", _curl_stub(log, serve_download=True))

    proc = _run(home, stubs, prefix, extra_env={"GH_HOST": "ghe.example.com"})

    requested = log.read_text() if log.exists() else ""
    assert f"/releases/download/{NEW_VERSION}/" in requested, requested + "\n" + proc.stderr
