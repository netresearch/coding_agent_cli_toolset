# Catalog Coverage

This file documents which tools have catalog entries and which use dedicated install scripts.

## Tools with Catalog Entries (57)

These tools use the catalog-based installation system with generic installers:

- ansible, ast-grep, aws, bandit, bat, black, codex, composer, curlie, dasel
- delta, direnv, dive, entr, fd, flake8, fx, fzf, gem, gemini, gh, git-absorb
- git-branchless, git-lfs, gitleaks, glab, golangci-lint, httpie, isort, just
- kubectl, ninja, npm, opengrep, parallel, pip, pipx, pnpm, poetry, pre-commit
- prettier, rga, ripgrep, ruff, sd, semgrep, shellcheck, shfmt, sponge, terraform
- tfsec, trivy, vault, watchexec, xsv, yarn, yq

## Tools with Dedicated Install Scripts

### Runtime Environments
These have their own complex installers in `scripts/`:
- **go** - `install_go.sh`
- **rust** - `install_rust.sh`
- **python** - `install_python.sh`
- **node** - `install_node.sh`

### Package Managers
Most now in catalog, one dedicated script:
- **uv** - `install_uv.sh` (special bootstrap installer)
- All others (pip, pipx, npm, pnpm, yarn, gem, composer, poetry, sponge) - Now in catalog!

### Docker Tools
- **docker** - `install_docker.sh` (uses official Docker install script)
- **docker-compose** - Typically installed with Docker

### System Tools
- **git** - System package (apt/dnf/brew)
- **ctags** - System package
- **sponge** - Part of moreutils package
- **prename** - System package (Perl rename)
- **rename.ul** - System package (util-linux rename)

### Other
- **gam** - Google Apps Manager (special installation)
- **claude** - Claude CLI (special installation)
- **ansible-core** - Subset of ansible package
- **eslint** - Node.js package (installed via npm)

## Installation Method Distribution

- **github_release_binary**: 32 tools
- **uv_tool**: 8 tools (Python CLI tools)
- **package_manager**: 10 tools (pip, pipx, poetry, npm, pnpm, yarn, gem, composer, sponge, entr)
- **hashicorp_zip**: 2 tools (terraform, vault)
- **aws_installer**: 1 tool (aws)
- **npm_global**: 1 tool (prettier)
- **script**: 1 tool (parallel)
- **dedicated_script**: 10 tools (runtimes: go, rust, python, node; special: uv, docker, git, ctags, gam)
- **system_package**: 2 tools (cscope, rename variants)

## Total: 72 tools tracked

- **57 tools** have catalog entries
- **10 tools** use dedicated scripts (runtimes + special cases)
- **5 tools** are system packages only

All installable tools either have catalog entries or use appropriate dedicated scripts.

## Bash completion coverage

Every catalog entry was audited for a bash-completion generator (sweep of
2026-07-22; each generator was executed and its output validated against
`complete -…` / `compgen ` / `COMPREPLY`, then checked to confirm it registers
the entry's own `binary_name`).

**40 entries declare `bash_completion`** — 39 `command`, 1 `source_path` (rbenv).

Declared (`command`): ast-grep, bat, black, codex, composer, dasel, delta, dive,
docker, fd, fx, gh, git-absorb, git-lfs, gitleaks, glab, golangci-lint, gup, jj,
just, kubectl, mlr, node, npm, parallel, pip, pipx, pnpm, poetry, ripgrep, ruff,
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
hyperfine, isort, jq, ninja, opengrep, php, pre-commit, prename, prettier,
python, qsv, rename.ul, ruby, ruby-build, sd, semgrep, shellcheck, shfmt,
sponge, templ, terraform, tfsec, tmux, tokei, tree, vault, wslu, xsv, yarn

(`git` and `docker` already ship completions via the distro `bash-completion`
package; `docker` is still declared so the generated script matches the
installed daemon version, and the XDG user directory takes precedence.)

**Not verifiable on the audit machine** — `codex`, `pip`, `pipx` were not
installed, so their generators come from official documentation rather than a
local run. The runtime validation makes this safe: if the command does not
produce a valid completion script, nothing is written.
