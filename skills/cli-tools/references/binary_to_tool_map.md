# Binary to Catalog Entry

A "command not found" names a binary; `install_tool.sh` wants the catalog
entry (`catalog/<name>.json`). Usually they are the same. The authoritative
lookup is the catalog itself:

```bash
jq -r 'select(.binary_name == "<binary>") | input_filename' "${CLAUDE_SKILL_DIR}/../../catalog/"*.json
```

`tests/test_claude_plugin.py` checks the first table below against the
catalog, so it cannot drift silently.

## Binary name differs from the catalog name

| Binary | Catalog entry |
|--------|---------------|
| `rg` | `ripgrep` |
| `ansible` | `ansible-core` |
| `difft` | `difftastic` |
| `file-rename` | `prename` |
| `python3` | `python` |
| `rustc` | `rust` |
| `awf` | `gh-aw-firewall` |
| `gws` | `google-workspace-cli` |
| `wslview` | `wslu` |
| `ble.sh` | `blesh` |

`docker` is the binary of two entries: `docker` (the engine and CLI) and
`compose` (the Compose plugin, invoked as `docker compose`).

## Distribution aliases

Debian and Ubuntu rename two binaries in their own packages:

| Command | Catalog entry | Note |
|---------|---------------|------|
| `fdfind` | `fd` | symlink to `~/.local/bin/fd` |
| `batcat` | `bat` | symlink to `~/.local/bin/bat` |

## Binaries that come with another entry

| Binaries | Install |
|----------|---------|
| `cargo`, `rustup` | `rust` |
| `gofmt` | `go` |
| `npx` | `node` (Node 26 no longer bundles `corepack`) |
| `pip3` | `pip` or `python` |
| `gem`, `irb` | `ruby` |

## Lookup order

1. A catalog file named like the binary (`catalog/<binary>.json`).
2. The `binary_name` lookup above.
3. The tables in this file.
4. Common variations: `tool3` → `tool`, `toolcat` → `tool`, `toolfind` → `tool`.
5. Otherwise the tool is not cataloged: install it with its own package
   manager, or add a catalog entry.
