# Catalog Coverage

This file documents which tools have catalog entries and how each one is installed.

## Catalog entries (107)

Counted from `catalog/*.json` on 2026-09-22. Every tool the audit tracks has a catalog entry; its `install_method` selects the installer (`scripts/installers/<method>.sh`). `dedicated_script` runs the script named in the entry's `script` field. `auto` goes through the reconciliation system (`reconcile_tool` in `scripts/lib/reconcile.sh`).

| install_method | Count | Tools |
|---|---|---|
| `github_release_binary` | 38 | ast-grep, curlie, dasel, direnv, dive, fx, fzf, gh, gh-aw, gh-aw-firewall, git-absorb, git-branchless, git-lfs, gitleaks, glab, golangci-lint, google-workspace-cli, gosec, herdr, jq, just, kubectl, mlr, ninja, opengrep, qsv, rga, sd, shellcheck, shfmt, symfony, tfsec, trivy, vhs, watchexec, xsv, yq, zellij |
| `dedicated_script` | 18 | blesh, byobu, claude, composer, docker, gem, go, node, parallel, pip, python, ruby, rust, tmux, tree, uv, wslu, yarn |
| `auto` | 13 | actionlint, bat, delta, difftastic, dust, fd, gup, hyperfine, jj, pnpm, ripgrep, scc, tokei |
| `uv_tool` | 12 | ansible-core, bandit, black, flake8, gam, git-filter-repo, httpie, isort, pre-commit, ruff, semgrep, trustmux |
| `package_manager` | 10 | bwrap, ctags, entr, git, php, pipx, poetry, prename, rename.ul, sponge |
| `npm_global` | 7 | bw, codex, eslint, gemini, jules, pi, prettier |
| `github_clone` | 2 | rbenv, ruby-build |
| `hashicorp_zip` | 2 | terraform, vault |
| `aws_installer` | 1 | aws |
| `docker_plugin` | 1 | compose |
| `gcloud_installer` | 1 | gcloud |
| `go_install` | 1 | templ |
| `npm_self_update` | 1 | npm |

## Bash completion coverage

Every catalog entry was audited for a bash-completion generator (sweep of
2026-07-22; each generator was executed and its output validated against
`complete -…` / `compgen ` / `COMPREPLY`, then checked to confirm it registers
the entry's own `binary_name`).

**42 entries declare `bash_completion`** — 41 `command`, 1 `source_path` (rbenv).

Declared (`command`): ast-grep, bat, black, codex, composer, dasel, delta, dive,
docker, fd, fx, gh, git-absorb, git-lfs, gitleaks, glab, golangci-lint, gup, herdr, jj,
jules, just, kubectl, mlr, node, npm, parallel, pip, pipx, pnpm, poetry, ripgrep, ruff,
scc, symfony, trivy, uv, vhs, watchexec, yq, zellij

Declared (`source_path`): rbenv (`completions/rbenv.bash`, under its `clone_path`)

### Deliberately excluded (a generator exists but must not be used)

The completion file is named after `binary_name`, so a script that registers a
*different* command would silently shadow another tool's completion:

| Tool | Why excluded |
|------|--------------|
| `gh-aw` | `gh-aw completion bash` emits **gh's** completion (`complete … __start_gh gh`); it never registers `gh-aw` and would shadow the distro `gh` completion |
| `rga` | `rga --generate complete-bash` forwards to ripgrep and returns ripgrep's script verbatim (registers `rg`) |
| `compose` | `binary_name` is `docker`; no compose-specific generator exists — `docker` already covers it |
| `fzf` | `fzf --bash` is full shell *integration* (key bindings, a global `complete -D` handler), not a completion script. Use `eval "$(fzf --bash)"` in `.bashrc` instead |
| `rust` | `rustup completions bash` registers `rustup`/`cargo`, never `rustc` |
| `gcloud` | Ships `completion.bash.inc`, but the entry has no `clone_path` for `source_path` to resolve against, and the file registers three commands (`gcloud`, `bq`, `gsutil`) in one lazily-loaded file |

### No bash completion available

actionlint, ansible-core, aws, bandit, claude, ctags, curlie, difftastic,
direnv, dust, entr, eslint, flake8, gam, gem, gemini, gh-aw-firewall, git,
git-branchless, git-filter-repo, go, google-workspace-cli, gosec, httpie,
hyperfine, isort, jq, ninja, opengrep, php, pi, pre-commit, prename, prettier,
python, qsv, rename.ul, ruby, ruby-build, sd, semgrep, shellcheck, shfmt,
sponge, templ, terraform, tfsec, tmux, tokei, tree, vault, wslu, xsv, yarn

(`git` and `docker` already ship completions via the distro `bash-completion`
package; `docker` is still declared so the generated script matches the
installed daemon version, and the XDG user directory takes precedence.)

**Not verifiable on the audit machine** — `codex`, `pip`, `pipx` were not
installed, so their generators come from official documentation rather than a
local run. The runtime validation makes this safe: if the command does not
produce a valid completion script, nothing is written.
