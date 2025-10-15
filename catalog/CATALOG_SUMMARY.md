# Catalog Summary

Total catalog files: 45

## Recently Added Tools (10)

### GitHub Release Binary Tools (6)

1. **git-lfs** - Git extension for versioning large files
   - Download pattern: tar.gz with version in filename
   - Architectures: x86_64 (amd64), aarch64 (arm64), armv7l (arm)
   - URL: `https://github.com/git-lfs/git-lfs/releases/download/{version}/git-lfs-linux-{arch}-{version}.tar.gz`

2. **git-absorb** - git commit --fixup, but automatic
   - Download pattern: tar.gz with musl Linux build
   - Architectures: x86_64 only (musl target)
   - URL: `https://github.com/tummychow/git-absorb/releases/download/{version_nov}/git-absorb-{version_nov}-x86_64-unknown-linux-musl.tar.gz`
   - Note: Limited ARM support with different target triple

3. **git-branchless** - High-velocity, monorepo-scale workflow for Git
   - Download pattern: tar.gz with musl Linux build
   - Architectures: x86_64 only
   - URL: `https://github.com/arxanas/git-branchless/releases/download/{version}/git-branchless-{version}-x86_64-unknown-linux-musl.tar.gz`

4. **direnv** - Unclutter your .profile with environment switcher
   - Download pattern: Direct binary (not an archive)
   - Architectures: x86_64 (amd64), aarch64 (arm64), armv7l (arm)
   - URL: `https://github.com/direnv/direnv/releases/download/{version}/direnv.linux-{arch}`

5. **golangci-lint** - Fast linters runner for Go
   - Download pattern: tar.gz with version in filename
   - Architectures: x86_64 (amd64), aarch64 (arm64), armv7l (armv6)
   - URL: `https://github.com/golangci/golangci-lint/releases/download/{version}/golangci-lint-{version_nov}-linux-{arch}.tar.gz`

6. **ninja** - Small build system with a focus on speed
   - Download pattern: zip files
   - Architectures: x86_64 (no suffix), aarch64 (-aarch64 suffix)
   - URL: `https://github.com/ninja-build/ninja/releases/download/{version}/ninja-linux{arch_suffix}.zip`
   - Note: x86_64 uses `ninja-linux.zip`, arm64 uses `ninja-linux-aarch64.zip`

### NPM Global Tool (1)

7. **prettier** - Opinionated code formatter
   - Install method: npm global
   - Package: prettier
   - Homepage: https://prettier.io

### UV Tool (1)

8. **ansible** - Radically simple IT automation
   - Install method: uv tool
   - Package: ansible
   - Note: Also handled by install_ansible.sh script with fallback to pipx

### Script-Based Installation (1)

9. **parallel** - GNU Parallel - shell tool for executing jobs in parallel
   - Install method: Custom script required
   - Source: GNU FTP server (ftp://ftp.gnu.org/gnu/parallel/)
   - Note: Not distributed via GitHub releases

### Package Manager Installation (1)

10. **entr** - Run arbitrary commands when files change
    - Install method: System package manager
    - Packages: entr (apt, dnf, pacman, brew)
    - Homepage: http://eradman.com/entrproject/
    - Note: No GitHub releases; use system package manager

## Installation Method Distribution

- **github_release_binary**: 35 tools
- **uv_tool**: 6 tools
- **npm_global**: 1 tool
- **script**: 2 tools
- **package_manager**: 1 tool

## Architecture Support Notes

Most tools support:
- x86_64 (amd64)
- aarch64 (arm64)
- armv7l (arm/armv6)

Exceptions:
- git-absorb: x86_64 only (musl build)
- git-branchless: x86_64 only
- Tools installed via uv/npm/package-manager: Architecture handled by installer

## URL Template Variables

- `{version}`: Full version string (e.g., v3.7.0)
- `{version_nov}`: Version without 'v' prefix (e.g., 3.7.0)
- `{arch}`: Architecture string from arch_map
- `{arch_suffix}`: Optional architecture suffix (ninja specific)
