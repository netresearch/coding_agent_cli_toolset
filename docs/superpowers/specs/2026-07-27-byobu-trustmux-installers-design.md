# Byobu and Trustmux Upstream Installers

## Goal

Add Byobu and Trustmux to the CLI tool catalog without relying on outdated
distribution packages. Both tools must install into the user's home directory,
participate in version auditing, and leave system-managed installations intact.

## Byobu

Byobu does not publish a standalone executable release. A dedicated installer
will therefore:

1. Resolve the newest stable tag from `dustinkirkland/byobu`.
2. Download the corresponding GitHub source archive with HTTP failure checks
   and bounded retries.
3. Build from the release source using `autogen.sh` when required, followed by
   `configure --prefix="$HOME/.local"`, `make`, and user-local installation.
4. Verify the installed command directly below `~/.local/bin` rather than
   relying on `PATH`.
5. Support `install`, `update`, and `uninstall` actions and refresh the local
   audit snapshot after successful installation.

Build logs must be retained until cleanup and their final lines printed when a
step fails. Temporary files must be removed on normal exit and interruption.

## Trustmux

Trustmux is officially published on PyPI. Its catalog entry will use the
existing `uv_tool` installer with package name and binary name `trustmux`.
This provides the newest stable published version as a user-local executable
without using the Ubuntu PPA or the Byobu distribution package.

## Catalog and audit

Each tool receives a catalog entry with its official homepage, upstream source,
binary name, version command, category, and installation method. The committed
upstream baseline will contain both tools. Catalog documentation counts will be
updated to match the resulting number of entries.

## Testing

Catalog tests will verify:

- both entries exist and contain the intended installation methods;
- Byobu points to its dedicated installer;
- Trustmux maps to the PyPI package and `trustmux` executable;
- all catalog JSON remains valid.

The dedicated Byobu installer must pass Bash syntax checks and Shellcheck. The
catalog test module and full Python test suite must remain green.

## Out of scope

- Installing development snapshots from a default branch.
- Replacing or deleting distribution-managed Byobu or Trustmux packages.
- Starting, enabling, pairing, or configuring the Trustmux daemon.
- Enabling Byobu automatically at login.
