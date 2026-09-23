# Shell Pitfalls

Shell constructs that report success, or emptiness, that is not real. Each one
below was hit in practice and then measured (bash 5.2, GNU grep 3.11,
ugrep 7.8.4, gh 2.98, npm 12); `tests/test_shell_pitfalls.py` re-runs the bash
ones. The common thread: **a status or a count is evidence only if the command
behind it actually ran and could have answered differently.**

## Contents

- Exit status
- Pipes and SIGPIPE
- Capturing output
- Reading records
- Quoting and expansion
- Signals and process groups
- Files written in place
- grep in the agent shell is ugrep
- Tool-specific traps

## Exit status

**`set -e` aborts on a failed command substitution before your diagnostic.**
`set -euo pipefail; v=$(false); echo "diagnose"` exits 1 and prints nothing.
Put the assignment in the condition, where `set -e` does not apply:

```bash
if ! v=$(some_cmd); then echo "some_cmd failed" >&2; exit 1; fi
[ -n "$v" ] || { echo "some_cmd printed nothing" >&2; exit 1; }
```

**`cond && action` as the last statement of a function returns 1 when `cond`
is false** — the normal path — and under `set -e` that kills the caller with
no output. Write `if cond; then action; fi`.

**`if ! cmd; then rc=$?` gives the negated status** (0 or 1), not the
command's. Use `rc=0; cmd || rc=$?`.

**The last command decides the status.** `cmd; echo done` reports 0 whatever
`cmd` did; so does `cmd | wc -l`, which also prints `0` when `cmd` failed
(`git -C /nonexistent ls-remote … | wc -l` → `0`, reading as "no branches").
Capture `rc=$?` first, and count only after the producing command succeeded.

**A verdict filter is not a gate.** `run_tests | grep -E 'SUCCESS|FAILURE' &&
git push` pushes on FAILURE: grep exits 0 because it matched a word. And
`n=$(… | grep -c x) && push` never pushes on zero matches, because `grep -c`
exits 1 when it counts 0 — while `n` still holds a plausible `0`. Gate on the
producing command's own status, or on the success token alone
(`grep -q '^SUCCESS'`).

## Pipes and SIGPIPE

**Under `pipefail`, a reader that stops early turns a match into a failure.**
`grep -q`, `head -1`, `awk '… {exit}'` and `sed -n '…q'` close the pipe at the
first hit; a writer with more to send dies of SIGPIPE, and `pipefail` makes its
141 the pipeline's status. With `t` holding 100,000 lines,
`set -o pipefail; printf '%s\n' "$t" | grep -q y` returned 141 in 8 of 8
runs — "not found", *because* it found something on line 1. Input that fits
the 64 KB pipe buffer, or a match only at the very end, usually passes, which
is why the bug survives testing. Hand the text over as a herestring instead —
it is not a pipeline:

```bash
out=$(producer)
grep -q pattern <<<"$out"     # 0 in 5 of 5 runs on the same input
```

## Capturing output

**`$(…)` strips every trailing newline.** Round-tripping a file through a
variable (`x=$(cat f); printf '%s' "$x" > f`) drops the final newline — a
1-byte difference that fails a byte-exact comparison. Write the producing
command straight to the file.

**`2>&1` inside a capture mixes warnings into the value.**
`ts=$(git show -s --format=%cI HEAD 2>&1)` holds the warning text whenever git
prints one and still exits 0. Capture stderr separately:
`ts=$(cmd 2>"$errfile")`.

**`curl -f` still prints its `-w` write-out on an HTTP error.**
`curl -fsSL -o /dev/null -w '%{url_effective}' <url>` exits 22 on a 404 and
prints the URL anyway, so a captured redirect target looks valid. Check the
exit status, and the shape of what came back.

## Reading records

**`IFS=$'\t' read` collapses empty fields.** Tab is IFS whitespace, and runs of
whitespace collapse however narrowly IFS is set: `a<TAB><TAB>b` reads as
`x=a y=b z=` — a column shift. Separate fields with a non-whitespace character
such as the ASCII unit separator `\037` (emit with jq `join("\u001f")`, read
with `IFS=$'\037'`): `x=a y= z=b`.

**`while read` skips a last line without a newline.** `printf 'a\nb' | while
read -r l` sees only `a`. Use `while read -r l || [ -n "$l" ]`.

**`for x in $var` splits and globs.** With `var='a*'` in a directory holding
`aa` and `ab`, the loop runs over `aa ab`, not `a*`. Split with
`read -ra arr <<<"$var"` and loop over `"${arr[@]}"`.

## Quoting and expansion

**Double quotes hand `$name` to the shell before the tool sees it.**
`grep "total: $sum"` searches for `total: ` when `sum` is unset and matches far
more than intended. A jq filter in double quotes fails the same way, loudly:
`jq ".x.\$ref"` reaches jq as `.x.$ref` and stops with
`syntax error, unexpected BINDING`. Single-quote patterns and program text.

**An unquoted heredoc executes backticks and `$(…)`.** `cat <<EOF` with
`` `echo RAN` `` in the body prints `RAN`; a commit message or PR body written
that way runs the commands it merely mentions. Quote the delimiter:
`<<'EOF'`.

**A same-line assignment reads the old value.**
`export A=$(cat token) B=$A` sets `B` to the empty string: the shell expands
`$A` before the assignment to its left takes effect. Use two statements.

**`bash -s` reads its script from stdin, and so does every command in it.**
In `ssh host 'bash -s' <<'EOF' … EOF`, a command that reads stdin (`cat`,
`mysql`, `docker exec -i`) swallows the rest of the script, which then never
runs — no error. Give such commands `</dev/null`, or copy the script over and
run it as a file.

## Signals and process groups

**`timeout(1)` runs its command in a process group of its own** (GNU
coreutils; `--foreground` keeps the caller's group). A signal sent to the
caller's group — Ctrl-C, or `kill -TERM -- -$PGID` — therefore does not reach
the command, and a `kill -TERM 0` inside the command does not reach the caller:
`bash -c 'trap "echo got" TERM; timeout 5 bash -c "kill -TERM 0"'` prints
nothing from the trap. It matters most in tests of interruption handling: a
test that makes a generator under `timeout` kill "its group" never interrupts
the code under test, and passes against code with no cleanup at all. Signal
the caller's process group instead, and wait for the command to finish before
asserting, because it outlives the signal.

## Files written in place

**`cmd > file` truncates `file` before `cmd` starts.** A failing `cmd` leaves
it empty (0 bytes). Write to a temporary file, check the status and the
content, then move it into place.

**`sed -i` exits 0 when nothing matched.** A pattern with the wrong
indentation leaves the file unchanged and reports success. Read the result
(`grep -n`, `git diff`), never the exit code.

## grep in the agent shell is ugrep

In Claude Code's Bash tool, `grep` is a shell function that runs the bundled
**ugrep** (7.8.4 here) with `--ignore-files --hidden -I` and `.git` excluded.
Scripts started with their own shebang get the system grep instead (GNU grep
3.11 here) — so a pattern checked interactively can behave differently inside
the script. `type -t grep` says which one a shell has. The differences that
bite:

- **Recursive search skips `.gitignore`d and binary files.** In a repository
  whose `.gitignore` lists `secret.txt`, `grep -rl needle .` returns only the
  tracked match; `/usr/bin/grep` returns both. Use `/usr/bin/grep` (or
  `rg --no-ignore`) when ignored files matter.
- **`grep -q -v` returns the wrong status.** For input holding a line that
  does not match, `grep -q -v '|completed|'` exits 1 under ugrep and 0 under
  GNU grep, so "is anything still open?" answers "no". Count instead:
  `grep -c -v … ` or `awk`, and compare the number.
- **`$` in the middle of a pattern is an anchor, not a literal.**
  `grep -c 'x $ROOT'` on the line `x $ROOT y` counts 0 under ugrep and 1
  under GNU grep. Escape it: `'x \$ROOT'`.
- **Two wide bounded wildcards exceed ugrep's complexity limit.**
  `grep -oE '.{0,60}needle.{0,60}'` exits 2 with `exceeds complexity limits`
  on any input — it fails while compiling the pattern; `.{0,40}…{0,40}` and a
  single `needle.{0,400}` pass. Use `-P`, which compiles it, or one bound.
- **An empty alternative inside a group is an error**: `grep -E 'a(x|)b'`
  exits 2 with `empty (sub)expression`, `-P` included. Fill the branch: `a(x)?b`.

## Tool-specific traps

**`npx` runs a package's binary only when both share a name.**
`npx --yes typescript@5 tsc` fails with
`could not determine executable to run`; `npx --yes -p typescript@5 tsc`
works. The failure matters most when the output is then counted:
`grep -c 'error TS'` on the failed run prints `0`, which reads as a clean
type check from a checker that never ran.

**`rg` without a path searches stdin when stdin is not a terminal.** In a
script, a pipeline or an agent's shell, `rg -l needle` waits on stdin — or
searches whatever is piped in and reports `<stdin>` — instead of the current
directory. Always pass the path: `rg -l needle .`.

**`gh api --jq` on an error still prints something.** On a 404, gh 2.98 writes
the error body (`{"message":"Not Found",…}`) to stdout and exits 1, so
`[ -n "$(gh api … --jq .name 2>/dev/null)" ]` is true for a repository that
does not exist. Test the exit status: `if gh api … >/dev/null 2>&1`.

**`gh` picks its host from `GH_HOST` or the enclosing repository.** Inside a
checkout of a GitHub Enterprise or other host, `gh api repos/o/r` goes there.
Pin it: `gh api --hostname github.com …`.

**Sourcing a `.env` exports git's identity variables.** `set -a; . ./.env`
with `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` placeholders makes the next commit
in that shell use them, whatever `git config` says. Commit through
`env -u GIT_AUTHOR_NAME -u GIT_AUTHOR_EMAIL -u GIT_COMMITTER_NAME -u GIT_COMMITTER_EMAIL git commit …`,
and check `git log -1 --format='%an <%ae>'` afterwards.

**`git archive` is the release tree, not the working tree.** Paths marked
`export-ignore` in `.gitattributes` — often `tests/` — are left out silently.
Copy with `git worktree add`, or `tar --exclude=.git`, when you need the whole
checkout.
