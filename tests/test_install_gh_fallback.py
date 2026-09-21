"""Installer tag lookup must survive a failing `gh api` call.

`gh api` prints the HTTP error body (e.g. a 401 "Bad credentials" for an
expired GITHUB_TOKEN exported by the Makefile) to *stdout* and exits 1.
The installers used to capture that body as if it were the tag list, so the
curl fallback never ran and the install aborted.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")

GH_401_BODY = """{
  "message": "Bad credentials",
  "documentation_url": "https://docs.github.com/rest",
  "status": "401"
}"""

BYOBU_TAGS_JSON = '[{"name":"trustmux-v7.19rc7"},{"name":"7.18"},{"name":"7.17"}]'
TMUX_LATEST_URL = "https://github.com/tmux/tmux/releases/tag/3.7b"


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    """Stub `gh` (fails with a 401 body on stdout) and `curl` (answers the API)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_stub(bin_dir, "gh", f"printf '%s' '{GH_401_BODY}'\nexit 1\n")
    _write_stub(
        bin_dir,
        "curl",
        f"""for arg in "$@"; do
  case "$arg" in
    https://api.github.com/repos/dustinkirkland/byobu/tags*) printf '%s' '{BYOBU_TAGS_JSON}'; exit 0 ;;
    https://github.com/tmux/tmux/releases/latest) printf '%s' '{TMUX_LATEST_URL}'; exit 0 ;;
  esac
done
exit 22
""",
    )
    return bin_dir


def _run_sourced(script: str, snippet: str, bin_dir: Path, home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "-c", f'source "{SCRIPTS / script}"\n{snippet}'],
        capture_output=True,
        text=True,
        env=env,
    )


@skip_on_windows
class TestGithubApiGet:
    """scripts/lib/install_strategy.sh::github_api_get — the shared lookup."""

    def test_prefers_gh_when_it_succeeds(self, fake_bin, tmp_path):
        _write_stub(fake_bin, "gh", f"printf '%s' '{BYOBU_TAGS_JSON}'\n")
        _write_stub(fake_bin, "curl", "exit 99\n")
        proc = _run_sourced("lib/install_strategy.sh", "github_api_get repos/dustinkirkland/byobu/tags", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == BYOBU_TAGS_JSON

    def test_falls_back_to_curl_and_says_so_when_gh_fails(self, fake_bin, tmp_path):
        proc = _run_sourced("lib/install_strategy.sh", "github_api_get repos/dustinkirkland/byobu/tags", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == BYOBU_TAGS_JSON
        assert "falling back" in proc.stderr

    def test_fails_cleanly_when_neither_source_answers(self, fake_bin, tmp_path):
        proc = _run_sourced("lib/install_strategy.sh", "github_api_get repos/nobody/nothing/tags", fake_bin, tmp_path)
        assert proc.returncode == 1
        assert proc.stdout == ""


@skip_on_windows
class TestGhErrorBodyFallback:
    def test_byobu_falls_back_to_curl_when_gh_fails(self, fake_bin, tmp_path):
        proc = _run_sourced("install_byobu.sh", "get_target_tag", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "7.18"
        assert "Cannot index" not in proc.stderr

    def test_byobu_uses_gh_result_when_gh_succeeds(self, fake_bin, tmp_path):
        _write_stub(fake_bin, "gh", f"printf '%s' '{BYOBU_TAGS_JSON}'\n")
        _write_stub(fake_bin, "curl", "exit 99\n")
        proc = _run_sourced("install_byobu.sh", "get_target_tag", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "7.18"

    def test_byobu_accepts_trustmux_prefixed_tags(self, fake_bin, tmp_path):
        # Real first page of the tags API after the trustmux rename: no plain tag on it
        tags = (
            '[{"name":"trustmux-v7.20rc5"},{"name":"trustmux-v7.19"},'
            '{"name":"trustmux-v7.19rc17"},{"name":"trustmux-v7.18"}]'
        )
        _write_stub(fake_bin, "gh", f"printf '%s' '{tags}'\n")
        proc = _run_sourced("install_byobu.sh", "get_target_tag", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "trustmux-v7.19"

    def test_byobu_prefers_plain_tag_for_equal_versions(self, fake_bin, tmp_path):
        tags = '[{"name":"trustmux-v7.19"},{"name":"7.19"},{"name":"7.18"}]'
        _write_stub(fake_bin, "gh", f"printf '%s' '{tags}'\n")
        proc = _run_sourced("install_byobu.sh", "get_target_tag", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "7.19"

    def test_tmux_falls_back_to_release_redirect_when_gh_fails(self, fake_bin, tmp_path):
        proc = _run_sourced("install_tmux.sh", "get_target_version", fake_bin, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "3.7b"

    def test_tree_reports_missing_version_instead_of_downloading_error_body(self, fake_bin, tmp_path):
        proc = _run_sourced("install_tree.sh", "install_tree", fake_bin, tmp_path)
        assert proc.returncode == 1
        assert "Could not determine latest version" in proc.stderr
        assert "Downloading" not in proc.stderr
