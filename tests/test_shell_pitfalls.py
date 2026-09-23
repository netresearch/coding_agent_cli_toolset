"""Re-run the bash claims in skills/cli-tools/references/shell-pitfalls.md.

Each case is its own ``bash -c`` with the status captured: wrapping variants in
functions or pipelines would let ``set -e`` and ``pipefail`` behave differently
from the construct the reference describes. If a bash release changes one of
these behaviours, this file fails and the reference needs updating.
"""

import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Shell script tests require POSIX shell")


def bash(script: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, **kwargs)


class TestExitStatus:
    def test_set_e_aborts_on_failed_substitution_before_the_diagnostic(self):
        proc = bash('set -euo pipefail; v=$(false); echo "diagnose"')
        assert (proc.returncode, proc.stdout) == (1, "")

    def test_assignment_in_the_condition_reaches_the_diagnostic(self):
        proc = bash("set -euo pipefail; if ! v=$(false); then echo diagnose; fi")
        assert proc.stdout == "diagnose\n"

    def test_and_list_as_last_statement_of_a_function_kills_the_caller(self):
        proc = bash("set -euo pipefail; f() { [[ 1 == 2 ]] && echo x; }; f; echo reached")
        assert (proc.returncode, proc.stdout) == (1, "")

    def test_if_not_hands_back_the_negated_status(self):
        assert bash("if ! (exit 5); then echo $?; fi").stdout == "0\n"
        assert bash("rc=0; (exit 5) || rc=$?; echo $rc").stdout == "5\n"

    def test_wc_counts_zero_for_a_command_that_failed(self):
        assert bash("git -C /nonexistent ls-remote --heads origin x 2>/dev/null | wc -l").stdout.strip() == "0"

    def test_a_verdict_filter_passes_on_failure(self):
        assert bash('echo FAILURE | grep -E "SUCCESS|FAILURE" >/dev/null && echo pushed').stdout == "pushed\n"

    def test_grep_count_assignment_fails_on_zero(self):
        assert bash("n=$(echo x | grep -c zz) && echo pushed || echo skipped $n").stdout == "skipped 0\n"


class TestPipes:
    def test_early_reader_under_pipefail_reports_the_match_as_a_failure(self):
        # 100,000 lines are far above the 64 KB pipe buffer, so printf (a
        # builtin, no pipe of its own) is still writing when grep -q exits on
        # line 1.
        proc = bash('set -o pipefail; t=$(yes | head -n 100000); printf "%s\\n" "$t" | grep -q y; echo $?')
        assert proc.stdout == "141\n"

    def test_herestring_does_not(self):
        proc = bash('set -o pipefail; t=$(yes | head -n 100000); grep -q y <<<"$t"; echo $?')
        assert proc.stdout == "0\n"


class TestCapture:
    def test_substitution_strips_every_trailing_newline(self):
        assert bash('x=$(printf "a\\n\\n\\n"); printf "%s" "$x"').stdout == "a"


class TestReadingRecords:
    def test_tab_ifs_collapses_an_empty_field(self):
        proc = bash("printf 'a\\t\\tb\\n' | { IFS=$'\\t' read -r x y z; echo \"$x|$y|$z\"; }")
        assert proc.stdout == "a|b|\n"

    def test_unit_separator_keeps_it(self):
        proc = bash("printf 'a\\037\\037b\\n' | { IFS=$'\\037' read -r x y z; echo \"$x|$y|$z\"; }")
        assert proc.stdout == "a||b\n"

    def test_while_read_skips_an_unterminated_last_line(self):
        assert bash("printf 'a\\nb' | while read -r l; do echo $l; done").stdout == "a\n"
        assert bash("printf 'a\\nb' | while read -r l || [ -n \"$l\" ]; do echo $l; done").stdout == "a\nb\n"

    def test_unquoted_for_globs(self, tmp_path):
        (tmp_path / "aa").touch()
        (tmp_path / "ab").touch()
        proc = bash('v="a*"; for p in $v; do echo -n "$p "; done; read -ra arr <<<"$v"; echo "${arr[@]}"', cwd=tmp_path)
        assert proc.stdout == "aa ab a*\n"


class TestQuoting:
    def test_unquoted_heredoc_runs_backticks(self):
        assert bash("cat <<EOF\nx `echo RAN` y\nEOF").stdout == "x RAN y\n"
        assert bash("cat <<'EOF'\nx `echo RAN` y\nEOF").stdout == "x `echo RAN` y\n"

    def test_same_line_assignment_reads_the_old_value(self):
        assert bash('export A=$(echo tok) B=$A; echo "[$B]"').stdout == "[]\n"

    def test_bash_s_loses_the_rest_of_the_script_to_a_stdin_reader(self):
        proc = bash("bash -s <<'EOF'\necho one\ncat >/dev/null\necho two\nEOF")
        assert proc.stdout == "one\n"


class TestFilesInPlace:
    def test_redirect_truncates_before_the_command_runs(self, tmp_path):
        target = tmp_path / "f"
        target.write_text("data\n")
        bash(f'no_such_command_zz >"{target}" 2>/dev/null')
        assert target.read_text() == ""

    @pytest.mark.skipif(sys.platform == "darwin", reason="BSD sed takes a suffix argument after -i")
    def test_sed_in_place_succeeds_without_a_match(self, tmp_path):
        target = tmp_path / "f"
        target.write_text("hello\n")
        proc = bash(f'sed -i s/zzz/y/ "{target}"')
        assert proc.returncode == 0
        assert target.read_text() == "hello\n"


def _has_gnu_timeout() -> bool:
    # BusyBox timeout has no --foreground and keeps the caller's group.
    if shutil.which("timeout") is None:
        return False
    proc = subprocess.run(["timeout", "--version"], capture_output=True, text=True)
    return "GNU coreutils" in proc.stdout


@pytest.mark.skipif(not _has_gnu_timeout(), reason="needs GNU coreutils timeout(1)")
class TestProcessGroups:
    def test_timeout_puts_its_command_in_a_group_of_its_own(self):
        proc = bash(
            'echo $(ps -o pgid= -p $$); timeout 5 bash -c "ps -o pgid= -p \\$\\$"; '
            'timeout --foreground 5 bash -c "ps -o pgid= -p \\$\\$"'
        )
        caller, child, foreground = proc.stdout.split()
        assert child != caller
        assert foreground == caller

    def test_kill_zero_inside_timeout_does_not_reach_the_caller(self):
        # Own session: should the assumption ever fail, the signal hits this
        # throwaway group, not the test runner.
        proc = bash(
            'trap "echo caller-got-TERM" TERM; timeout 5 bash -c "kill -TERM 0"; echo survived',
            start_new_session=True,
        )
        assert "caller-got-TERM" not in proc.stdout
        assert proc.stdout.strip().endswith("survived")
