#!/usr/bin/env bash
set -euo pipefail

# Install/update/uninstall simple, language-agnostic tools.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"
ONLY_TOOL="${2:-}"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
PREFIX="${PREFIX:-$HOME/.local}"
# Prefer /usr/local/bin to override system binaries when possible, but fall back
# to user bin when we cannot write and passwordless sudo isn't available.
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
  BIN_DIR="/usr/local/bin"
elif [ -d "/usr/local/bin" ] && command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  BIN_DIR="/usr/local/bin"
else
  BIN_DIR="$PREFIX/bin"
fi
mkdir -p "$BIN_DIR" 2>/dev/null || true
# Installer helper (use sudo only if BIN_DIR is /usr/local/bin and passwordless sudo available)
if [ "$BIN_DIR" = "/usr/local/bin" ]; then
  if [ -w "$BIN_DIR" ]; then INSTALL="install -m 0755"; else INSTALL="sudo install -m 0755"; fi
  if [ -w "$BIN_DIR" ]; then RM="rm -f"; else RM="sudo rm -f"; fi
else
  INSTALL="install -m 0755"
  RM="rm -f"
fi

get_version() {
  local t="$1" cmd vers
  case "$t" in
    git) cmd="$(command -v git || true)" ;;
    gh) cmd="$(command -v gh || true)" ;;
    fd) cmd="$(command -v fd || command -v fdfind || true)" ;;
    ripgrep) cmd="$(command -v rg || true)" ;;
    jq) cmd="$(command -v jq || true)" ;;
    yq) cmd="$(command -v yq || true)" ;;
    bat) cmd="$(command -v bat || command -v batcat || true)" ;;
    delta) cmd="$(command -v delta || true)" ;;
    just) cmd="$(command -v just || true)" ;;
    fzf) cmd="$(command -v fzf || true)" ;;
    curlie) cmd="$(command -v curlie || true)" ;;
    dive) cmd="$(command -v dive || true)" ;;
    trivy) cmd="$(command -v trivy || true)" ;;
    gitleaks) cmd="$(command -v gitleaks || true)" ;;
    git-absorb) cmd="$(command -v git-absorb || true)" ;;
    git-branchless) cmd="$(command -v git-branchless || true)" ;;
    eslint) cmd="$(command -v eslint || true)" ;;
    prettier) cmd="$(command -v prettier || true)" ;;
    shfmt) cmd="$(command -v shfmt || true)" ;;
    shellcheck) cmd="$(command -v shellcheck || true)" ;;
    fx) cmd="$(command -v fx || true)" ;;
    entr) cmd="$(command -v entr || true)" ;;
    glab) cmd="$(command -v glab || true)" ;;
    *) cmd="" ;;
  esac
  if [ -z "$cmd" ]; then return 0; fi
  case "$t" in
    git)
      # Emit semantic version only (e.g., 2.51.0)
      "$cmd" --version 2>/dev/null | awk 'NR==1{print $3}' | head -n1; return 0 ;;
    gh)
      # gh --version first line includes "gh version X.Y.Z (...)"
      "$cmd" --version 2>/dev/null | awk 'NR==1 && $1=="gh" && $2=="version"{print $3}'; return 0 ;;
    fx)
      # Prefer reading version from adjacent package.json (Node variant), else fallback to CLI flags
      local real dir pkg
      real="$(readlink -f "$cmd" 2>/dev/null || echo "$cmd")"
      dir="$(dirname "$real")"
      pkg="$dir/package.json"
      if [ -f "$pkg" ] && command -v jq >/dev/null 2>&1; then
        jq -r .version "$pkg" 2>/dev/null | head -n1; return 0
      fi
      "$cmd" -v 2>/dev/null | head -n1 && return 0
      "$cmd" --version 2>/dev/null | head -n1 && return 0
      "$cmd" version 2>/dev/null | head -n1 && return 0
      return 0 ;;
    curlie)
      "$cmd" version 2>/dev/null | head -n1; return 0 ;;
    shellcheck)
      # ShellCheck prints multi-line version output; extract numeric from the 'version:' line
      if out="$($cmd -V 2>/dev/null)"; then
        printf '%s\n' "$out" | awk -F': ' '/^version:/ {print $2; exit}'; return 0
      fi
      # Fallback: scan --version output for a semantic version number
      "$cmd" --version 2>/dev/null | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n1; return 0 ;;
    entr)
      # entr prints version as "release: X.Y" on usage output; no stable --version flag
      "$cmd" 2>&1 | awk '/^release:/ {print $2; exit}'; return 0 ;;
    *)
      "$cmd" --version 2>/dev/null | head -n1; return 0 ;;
  esac
}

go_bin_path() { local p; p="$(go env GOBIN 2>/dev/null || true)"; if [ -z "$p" ]; then p="$(go env GOPATH 2>/dev/null || true)/bin"; fi; printf '%s' "$p"; }

install_ctags() {
  # Prefer upstream universal-ctags built from source and packaged via checkinstall
  # to ensure clean uninstall and latest features. Fallback to package managers.
  if have brew; then brew install universal-ctags || brew install ctags; return; fi

  # If using apt-based systems, attempt source build with checkinstall
  if have apt-get; then
    local target_ver pkg_ver bin ctags_ver tmp builddir prefix
    target_ver="${CTAGS_VERSION:-${CTAGS_VERSION_PIN:-}}"
    if [ -z "$target_ver" ]; then
      # Derive from latest_versions.json if present; otherwise use fallback v6.2.0
      if [ -f "$DIR/../latest_versions.json" ] && command -v jq >/dev/null 2>&1; then
        target_ver="$(jq -r '.ctags' "$DIR/../latest_versions.json" 2>/dev/null | sed 's/^v//')"
      fi
      [ -n "$target_ver" ] || target_ver="6.2.0"
    fi

    bin="$(command -v ctags || true)"
    ctags_ver="$(ctags --version 2>/dev/null | sed -n 's/^Universal Ctags \([0-9.][0-9.]*\).*/\1/p')"
    if [ -n "$ctags_ver" ] && [ "$ctags_ver" = "$target_ver" ] && [ "$bin" = "/usr/local/bin/ctags" ]; then
      # Already at desired version under /usr/local; ensure alternatives are set and return
      sudo update-alternatives --install /usr/bin/ctags ctags /usr/local/bin/ctags 100 >/dev/null 2>&1 || true
      sudo update-alternatives --set ctags /usr/local/bin/ctags >/dev/null 2>&1 || true
      return
    fi

    sudo apt-get update || true
    # Minimal build deps
    sudo apt-get install -y \
      build-essential autoconf automake libtool pkg-config \
      git libxml2-dev libyaml-dev libjansson-dev libpcre2-dev libssl-dev \
      checkinstall jq || true

    tmp="$(mktemp -d)"
    builddir="$tmp/ctags"
    prefix="/usr/local"
    if [ ! -d "$builddir" ]; then
      git clone https://github.com/universal-ctags/ctags.git "$builddir" >/dev/null 2>&1 || true
    fi
    if [ -d "$builddir" ]; then
      (
        cd "$builddir" &&
        git fetch --tags >/dev/null 2>&1 || true &&
        git checkout "v${target_ver}" >/dev/null 2>&1 || true &&
        ./autogen.sh >/dev/null 2>&1 || true &&
        ./configure --prefix="$prefix" >/dev/null 2>&1 || true &&
        make -j"$(nproc)" >/dev/null 2>&1 || true
      )
      if [ -f "$builddir/ctags" ] || [ -f "$builddir/ctags.exe" ] || [ -x "$builddir/ctags" ]; then
        # Package and install via checkinstall for clean uninstall
        (
          cd "$builddir" &&
          sudo checkinstall -y \
            --pkgname=universal-ctags \
            --pkgversion="${target_ver}" \
            --provides=ctags \
            --backup=no \
            --install=yes \
            --fstrans=no \
            make install >/dev/null 2>&1 || true
        )
        # Register with update-alternatives
        sudo update-alternatives --install /usr/bin/ctags ctags "$prefix/bin/ctags" 100 >/dev/null 2>&1 || true
        sudo update-alternatives --set ctags "$prefix/bin/ctags" >/dev/null 2>&1 || true
        # Validate; if not present, fall back to apt package
        if command -v ctags >/dev/null 2>&1 && ctags --version >/dev/null 2>&1; then
          return
        fi
      fi
    fi

    # Fallback to distro packages if source build path failed
    (sudo apt-get install -y universal-ctags || sudo apt-get install -y exuberant-ctags ctags) && return
  fi
}

install_entr() {
  if have brew; then brew install entr; return; fi
  # Try to build latest from GitHub to ensure up-to-date version
  local tmp tag url srcdir cores rel html file prefix_dir SUDO_CMD
  tmp="$(mktemp -d)"
  # 1) Try to discover latest tag via redirect
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/eradman/entr/releases/latest | awk -F'/' '{print $NF}')"
  # 2) Prefer an explicit release asset like entr-<ver>.tar.gz (parse HTML) to avoid tag name quirks
  html="$(curl -fsSL https://github.com/eradman/entr/releases/latest 2>/dev/null || true)"
  if [ -n "$html" ]; then
    rel="$(printf '%s' "$html" | grep -Eo '/eradman/entr/releases/download/[^" ]+/entr-[0-9.]+\.tar\.gz' | head -n1)"
  fi
  if [ -n "$rel" ]; then
    url="https://github.com${rel}"
  elif [ -n "$tag" ]; then
    # Fallback to tag tarball
    url="https://github.com/eradman/entr/archive/refs/tags/${tag}.tar.gz"
  else
    url=""
  fi
  if [ -n "$url" ] && curl -fsSL "$url" -o "$tmp/entr.tgz"; then
    if tar -C "$tmp" -xzf "$tmp/entr.tgz" >/dev/null 2>&1; then
      # Extracted dir could be entr-<ver> or entr-<hash>
      srcdir="$(find "$tmp" -maxdepth 1 -type d -name 'entr-*' | head -n1)"
      if [ -z "$srcdir" ]; then srcdir="$(find "$tmp" -maxdepth 2 -type d -name 'entr*' | head -n1)"; fi
      if [ -n "$srcdir" ] && [ -d "$srcdir" ]; then
        # Ensure basic build deps
        if have apt-get; then
          sudo apt-get update >/dev/null 2>&1 || true
          sudo apt-get install -y build-essential pkg-config libbsd-dev >/dev/null 2>&1 || true
        fi
        cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
        (
          cd "$srcdir" && ( [ -x ./configure ] && sh ./configure || true ) && make -j"$cores"
        ) >/dev/null 2>&1 || true
        # Try make install when possible
        prefix_dir="$(dirname "$BIN_DIR")"
        if [ "$BIN_DIR" = "/usr/local/bin" ] && [ ! -w "$BIN_DIR" ]; then SUDO_CMD="sudo"; else SUDO_CMD=""; fi
        (
          cd "$srcdir" && ${SUDO_CMD} make install PREFIX="$prefix_dir"
        ) >/dev/null 2>&1 || true
        # If not installed by make, locate binary and install manually
        file="$(find "$srcdir" -type f -name entr -perm -111 | head -n1)"
        if [ -n "$file" ] && [ -f "$file" ]; then $INSTALL "$file" "$BIN_DIR/entr" && return; fi
        # If installed into prefix/bin already, accept success
        if command -v entr >/dev/null 2>&1; then return; fi
      fi
    fi
  fi
  # Fallback to system package if build path failed
  if have apt-get; then sudo apt-get update && sudo apt-get install -y entr; return; fi
}

install_parallel() {
  # Prefer upstream GNU FTP to get latest/pinned release; fall back to package manager
  if have brew; then brew install parallel; return; fi
  local tmp url name ext srcdir tarflag ver prefix_dir SUDO_CMD
  tmp="$(mktemp -d)"
  ver="${PARALLEL_VERSION:-}"
  # Discover latest version if not pinned via PARALLEL_VERSION
  if [ -z "$ver" ]; then
    if curl -fsSL "https://ftp.gnu.org/gnu/parallel/" -o "$tmp/index.html"; then
      name="$(grep -Eo 'parallel-[0-9]{8}\.tar\.(bz2|xz|gz)' "$tmp/index.html" | sort -V | tail -n1)" || true
      if [ -n "$name" ]; then
        ver="$(printf '%s' "$name" | sed -E 's/parallel-([0-9]{8})\.tar\.(bz2|xz|gz)/\1/')"
      fi
    fi
  fi
  # Try to download from GNU ftpmirror first
  if [ -n "$ver" ]; then
    for ext in tar.bz2 tar.xz tar.gz; do
      name="parallel-${ver}.${ext}"
      url="https://ftpmirror.gnu.org/parallel/${name}"
      if curl -fsSL "$url" -o "$tmp/${name}"; then
        case "$ext" in
          tar.bz2) tarflag="-xjf" ;;
          tar.xz)  tarflag="-xJf" ;;
          tar.gz)  tarflag="-xzf" ;;
          *) tarflag="-xjf" ;;
        esac
        if tar -C "$tmp" $tarflag "$tmp/${name}" >/dev/null 2>&1; then
          srcdir="$(find "$tmp" -maxdepth 1 -type d -name "parallel-*" | head -n1)"
          if [ -n "$srcdir" ] && [ -d "$srcdir" ]; then
            # Determine prefix from BIN_DIR (e.g., /usr/local/bin -> /usr/local)
            prefix_dir="$(dirname "$BIN_DIR")"
            # Use sudo for system prefix if needed (only when passwordless sudo available per earlier logic)
            if [ "$BIN_DIR" = "/usr/local/bin" ] && [ ! -w "$BIN_DIR" ]; then SUDO_CMD="sudo"; else SUDO_CMD=""; fi
            # Ensure minimal build deps on apt systems
            if have apt-get; then sudo apt-get update >/dev/null 2>&1 || true; sudo apt-get install -y make perl build-essential >/dev/null 2>&1 || true; fi
            (
              cd "$srcdir" &&
              ./configure --prefix="$prefix_dir" >/dev/null 2>&1 || true &&
              make >/dev/null 2>&1 || true &&
              ${SUDO_CMD} make install >/dev/null 2>&1 || true
            )
            # If make install failed for any reason, fall back to copying the script
            if ! command -v parallel >/dev/null 2>&1 || ! parallel --version >/dev/null 2>&1; then
              if [ -f "$srcdir/src/parallel" ]; then
                $INSTALL "$srcdir/src/parallel" "$BIN_DIR/parallel" && return
              fi
            else
              return
            fi
          fi
        fi
      fi
    done
  fi
  # Fallback to system package if all else fails
  if have apt-get; then sudo apt-get update && sudo apt-get install -y parallel; return; fi
}

install_ast_grep() {
  if have brew; then brew install ast-grep; return; fi
  if command -v cargo >/dev/null 2>&1; then cargo install ast-grep; return; fi
}

install_direnv() {
  if have brew; then brew install direnv; return; fi
  # Try latest GitHub release (prefer official binary over distro package)
  local tmp tag os arch name url
  tmp="$(mktemp -d)"
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/direnv/direnv/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    case "$OS" in
      linux) os="linux" ;;
      darwin) os="darwin" ;;
      *) os="linux" ;;
    esac
    case "$ARCH" in
      x86_64|amd64) arch="amd64" ;;
      aarch64|arm64) arch="arm64" ;;
      *) arch="amd64" ;;
    esac
    name="direnv.${os}-${arch}"
    url="https://github.com/direnv/direnv/releases/download/${tag}/${name}"
    if curl -fsSL "$url" -o "$tmp/direnv"; then
      chmod +x "$tmp/direnv" || true
      $INSTALL "$tmp/direnv" "$BIN_DIR/direnv" && return
    fi
  fi
  # Fallback to apt if GitHub download fails
  if have apt-get; then sudo apt-get update && sudo apt-get install -y direnv; return; fi
}

install_git() {
  if have brew; then brew install git || brew upgrade git || true; return; fi
  if have apt-get; then
    # Prefer official git-core PPA on Ubuntu-family to get newer Git than distro
    case "$(os_id)" in
      ubuntu|linuxmint|pop)
        sudo apt-get update || true
        sudo apt-get install -y software-properties-common ca-certificates gnupg || true
        sudo add-apt-repository -y ppa:git-core/ppa || true
        sudo apt-get update || true
        sudo apt-get install -y git || true
        ;;
      *)
        sudo apt-get update && (sudo apt-get install -y --only-upgrade git || sudo apt-get install -y git)
        ;;
    esac
    # If still behind upstream, build latest from source into /usr/local
    local installed tag latest tmp src nproc_val
    installed="$(get_version git || true)"
    tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/git/git/releases/latest | awk -F'/' '{print $NF}')"
    latest="${tag#v}"
    if [ -n "$installed" ] && [ -n "$latest" ]; then
      if command -v dpkg >/dev/null 2>&1; then
        if dpkg --compare-versions "$installed" ge "$latest"; then return; fi
      else
        if [ "$(printf '%s\n%s\n' "$latest" "$installed" | sort -V | tail -n1)" = "$installed" ]; then return; fi
      fi
    fi
    sudo apt-get update || true
    sudo apt-get install -y build-essential dh-autoreconf libssl-dev libcurl4-gnutls-dev libexpat1-dev gettext zlib1g-dev tcl libpcre2-dev libzstd-dev || true
    tmp="$(mktemp -d)"
    if curl -fsSL "https://github.com/git/git/archive/refs/tags/${tag}.tar.gz" -o "$tmp/git.tar.gz"; then
      if tar -C "$tmp" -xzf "$tmp/git.tar.gz" >/dev/null 2>&1; then
        src="$(find "$tmp" -maxdepth 1 -type d -name 'git-*' | head -n1)"
        if [ -n "$src" ] && [ -d "$src" ]; then
          nproc_val="$(command -v nproc >/dev/null 2>&1 && nproc || echo 2)"
          (
            cd "$src" &&
            make configure >/dev/null 2>&1 || true &&
            ./configure --prefix=/usr/local >/dev/null 2>&1 || true &&
            make -j"$nproc_val" all >/dev/null 2>&1 &&
            sudo make install >/dev/null 2>&1
          ) || true
        fi
      fi
    fi
    return
  fi
}

install_gh() {
  if have brew; then brew install gh || brew upgrade gh || true; return; fi
  # Try GitHub release binary (cli/cli)
  local tmp tag ver url name file
  tmp="$(mktemp -d)"
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/cli/cli/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    ver="${tag#v}"
    case "$ARCH" in
      x86_64|amd64) name="gh_${ver}_linux_amd64.tar.gz" ;;
      aarch64|arm64) name="gh_${ver}_linux_arm64.tar.gz" ;;
      *) name="gh_${ver}_linux_amd64.tar.gz" ;;
    esac
    url="https://github.com/cli/cli/releases/download/${tag}/${name}"
    if curl -fsSL "$url" -o "$tmp/gh.tgz"; then
      if tar -C "$tmp" -xzf "$tmp/gh.tgz" >/dev/null 2>&1; then
        file="$(find "$tmp" -type f -path "*/bin/gh" -perm -111 | head -n1)"
        if [ -n "$file" ] && [ -f "$file" ]; then $INSTALL "$file" "$BIN_DIR/gh" && return; fi
      fi
    fi
  fi
  # Fallback to apt (available if GitHub apt repo configured)
  if have apt-get; then sudo apt-get update && sudo apt-get install -y gh || true; fi
}

install_fd() {
  if have fd || have fdfind; then return; fi
  if have brew; then brew install fd; return; fi
  if have cargo; then cargo install fd-find; return; fi
  if have apt-get; then sudo apt-get update && sudo apt-get install -y fd-find; return; fi
}

install_fzf() {
  # Prefer latest from Homebrew or GitHub release; avoid apt unless no alternative
  if have brew; then brew install fzf; return; fi
  # Install latest binary from GitHub
  local tag ver tmp url
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/junegunn/fzf/releases/latest | awk -F'/' '{print $NF}')"
  ver="${tag#v}"
  if [ -n "$ver" ]; then
    tmp="$(mktemp -d)"
    url="https://github.com/junegunn/fzf/releases/download/${tag}/fzf-${ver}-linux_amd64.tar.gz"
    curl -fsSL "$url" -o "$tmp/fzf.tar.gz"
    tar -C "$tmp" -xzf "$tmp/fzf.tar.gz" || true
    if [ -f "$tmp/fzf" ]; then
      install -m 0755 "$tmp/fzf" "$BIN_DIR/fzf"
      return
    fi
  fi
  # Fallbacks
  if have apt-get; then sudo apt-get update && sudo apt-get install -y fzf; return; fi
  git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf" && "$HOME/.fzf/install" --no-update-rc --key-bindings --completion --no-bash --no-fish --no-zsh || true
}

install_rg() {
  if have rg; then return; fi
  if have brew; then brew install ripgrep; return; fi
  if have cargo; then cargo install ripgrep; return; fi
  if have apt-get; then sudo apt-get update && sudo apt-get install -y ripgrep; return; fi
}

install_jq() {
  if have jq; then return; fi
  if have brew; then brew install jq; return; fi
  # Try latest GitHub release binary (jqlang/jq)
  local tag url tmp
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/jqlang/jq/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    tmp="$(mktemp -d)"
    for name in jq-linux-amd64 jq-linux64 jq-linux-x86_64; do
      url="https://github.com/jqlang/jq/releases/download/${tag}/${name}"
      if curl -fsSL "$url" -o "$tmp/jq"; then
        chmod +x "$tmp/jq" || true
        $INSTALL "$tmp/jq" "$BIN_DIR/jq" && return
      fi
    done
  fi
  # Fallback to apt if nothing else worked
  if have apt-get; then sudo apt-get update && sudo apt-get install -y jq; return; fi
}

install_yq() {
  if [ "${FORCE:-0}" != "1" ] && have yq; then return; fi
  if have brew; then brew install yq; return; fi
  # Prefer GitHub binary (map arch names to upstream asset names)
  local tmp os arch url
  tmp="$(mktemp -d)"
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  case "$ARCH" in
    x86_64|amd64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) arch="amd64" ;;
  esac
  url="https://github.com/mikefarah/yq/releases/latest/download/yq_${os}_${arch}"
  if curl -fsSL "$url" -o "$tmp/yq"; then
    chmod +x "$tmp/yq" || true
    $INSTALL "$tmp/yq" "$BIN_DIR/yq" && return
  fi
  # Fallback to apt
  if have apt-get; then sudo apt-get update && sudo apt-get install -y yq; return; fi
}

install_bat() {
  if have bat || have batcat; then return; fi
  if have brew; then brew install bat; return; fi
  if have cargo; then cargo install bat; return; fi
  if have apt-get; then sudo apt-get update && sudo apt-get install -y bat || true; fi
}

install_delta() {
  if have delta; then return; fi
  if have brew; then brew install git-delta; return; fi
  if have cargo; then cargo install git-delta; return; fi
}

install_curlie() {
  if have brew; then brew install curlie; return; fi
  # Try GitHub latest release via redirect to get tag, then download correct asset
  local tmp tag ver arch url name file AUTH
  tmp="$(mktemp -d)"
  if [ -n "${GITHUB_TOKEN:-}" ]; then AUTH=( -H "Authorization: Bearer ${GITHUB_TOKEN}" ); else AUTH=(); fi
  tag="$(curl -fsSIL ${AUTH[@]} -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' https://github.com/rs/curlie/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    ver="${tag#v}"
    case "$ARCH" in
      x86_64|amd64) arch="x86_64|amd64" ;;
      aarch64|arm64) arch="arm64|aarch64" ;;
      *) arch="x86_64|amd64" ;;
    esac
    # Try a set of common asset name patterns produced by goreleaser
    for name in \
      "curlie_${ver}_Linux_x86_64.tar.gz" \
      "curlie_${ver}_linux_x86_64.tar.gz" \
      "curlie_${ver}_linux_amd64.tar.gz" \
      "curlie_${ver}_Linux_amd64.tar.gz" \
      "curlie_${ver}_Linux_arm64.tar.gz" \
      "curlie_${ver}_linux_arm64.tar.gz" \
      "curlie_${ver}_linux_${ARCH}.tar.gz"; do
      url="https://github.com/rs/curlie/releases/download/${tag}/${name}"
      if curl -fsSL ${AUTH[@]} -H "User-Agent: cli-audit" "$url" -o "$tmp/curlie.tgz"; then
        tar -C "$tmp" -xzf "$tmp/curlie.tgz" || true
        if [ -f "$tmp/curlie" ]; then $INSTALL "$tmp/curlie" "$BIN_DIR/curlie"; return; fi
        # If unpacked into a directory, locate the binary
        file="$(tar -tzf "$tmp/curlie.tgz" 2>/dev/null | awk -F/ '/(^|/)curlie$/{print $0; exit}')"
        if [ -n "$file" ] && [ -f "$tmp/$file" ]; then $INSTALL "$tmp/$file" "$BIN_DIR/curlie"; return; fi
      fi
    done
  fi
  # Fallback: go install (may report 0.0.0-LOCAL)
  if command -v go >/dev/null 2>&1; then GO111MODULE=on go install github.com/rs/curlie@latest && $INSTALL "$(go_bin_path)/curlie" "$BIN_DIR/curlie"; return; fi
}

install_dive() {
  if have brew; then brew install dive; return; fi
  # GitHub release binary
  local tag url tmp name
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/wagoodman/dive/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    tmp="$(mktemp -d)"
    name="dive_${tag#v}_linux_amd64.tar.gz"
    url="https://github.com/wagoodman/dive/releases/download/${tag}/${name}"
    if curl -fsSL "$url" -o "$tmp/dive.tgz"; then
      tar -C "$tmp" -xzf "$tmp/dive.tgz" || true
      if [ -f "$tmp/dive" ]; then $INSTALL "$tmp/dive" "$BIN_DIR/dive"; return; fi
    fi
  fi
}

install_trivy() {
  if have brew; then brew install trivy; return; fi
  # GitHub release binary
  local tag tmp url name
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/aquasecurity/trivy/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    tmp="$(mktemp -d)"
    name="trivy_${tag#v}_Linux-64bit.tar.gz"
    url="https://github.com/aquasecurity/trivy/releases/download/${tag}/${name}"
    if curl -fsSL "$url" -o "$tmp/trivy.tgz"; then
      tar -C "$tmp" -xzf "$tmp/trivy.tgz" || true
      if [ -f "$tmp/trivy" ]; then $INSTALL "$tmp/trivy" "$BIN_DIR/trivy"; return; fi
    fi
  fi
}

install_gitleaks() {
  if have brew; then brew install gitleaks; return; fi
  # GitHub release binary
  local tag tmp url name
  tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/gitleaks/gitleaks/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    tmp="$(mktemp -d)"
    name="gitleaks_${tag#v}_linux_x64.tar.gz"
    url="https://github.com/gitleaks/gitleaks/releases/download/${tag}/${name}"
    if curl -fsSL "$url" -o "$tmp/gitleaks.tgz"; then
      tar -C "$tmp" -xzf "$tmp/gitleaks.tgz" || true
      if [ -f "$tmp/gitleaks" ]; then $INSTALL "$tmp/gitleaks" "$BIN_DIR/gitleaks"; return; fi
    fi
  fi
}

install_git_absorb() {
  if have brew; then brew install git-absorb; return; fi
  if command -v cargo >/dev/null 2>&1; then cargo install git-absorb; return; fi
}

install_git_branchless() {
  if have brew; then brew install git-branchless; return; fi
  if command -v cargo >/dev/null 2>&1; then cargo install git-branchless; return; fi
}

install_eslint() {
  ensure_nvm_loaded || true
  if command -v npm >/dev/null 2>&1; then 
    if env -u PREFIX npm install -g eslint >/dev/null 2>&1; then return; fi
    env -u PREFIX npm install -g --prefix "$HOME/.local" eslint || true
    if [ -x "$HOME/.local/bin/eslint" ]; then $INSTALL "$HOME/.local/bin/eslint" "$BIN_DIR/eslint"; return; fi
  fi
  if have brew; then brew install eslint; return; fi
}

install_prettier() {
  ensure_nvm_loaded || true
  if command -v npm >/dev/null 2>&1; then 
    if env -u PREFIX npm install -g prettier >/dev/null 2>&1; then return; fi
    env -u PREFIX npm install -g --prefix "$HOME/.local" prettier || true
    if [ -x "$HOME/.local/bin/prettier" ]; then $INSTALL "$HOME/.local/bin/prettier" "$BIN_DIR/prettier"; return; fi
  fi
  if have brew; then brew install prettier; return; fi
}

install_shfmt() {
  if command -v go >/dev/null 2>&1; then GO111MODULE=on go install mvdan.cc/sh/v3/cmd/shfmt@latest && $INSTALL "$(go_bin_path)/shfmt" "$BIN_DIR/shfmt"; return; fi
  if have brew; then brew install shfmt; return; fi
}

install_shellcheck() {
  if have brew; then brew install shellcheck; return; fi
  # Try GitHub release binary first to get latest version
  local tmp tag arch name url file AUTH
  tmp="$(mktemp -d)"
  if [ -n "${GITHUB_TOKEN:-}" ]; then AUTH=( -H "Authorization: Bearer ${GITHUB_TOKEN}" ); else AUTH=(); fi
  tag="$(curl -fsSIL ${AUTH[@]} -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' https://github.com/koalaman/shellcheck/releases/latest | awk -F'/' '{print $NF}')"
  case "$ARCH" in
    x86_64|amd64) arch="x86_64" ;;
    aarch64|arm64) arch="aarch64" ;;
    armv6*|armv7*|arm*) arch="armv6" ;;
    *) arch="x86_64" ;;
  esac
  if [ -n "$tag" ]; then
    name="shellcheck-${tag}.linux.${arch}.tar.xz"
    url="https://github.com/koalaman/shellcheck/releases/download/${tag}/${name}"
    if curl -fsSL ${AUTH[@]} -H "User-Agent: cli-audit" "$url" -o "$tmp/sc.tar.xz"; then
      # Extract and install the 'shellcheck' binary
      if tar -C "$tmp" -xJf "$tmp/sc.tar.xz" >/dev/null 2>&1; then
        file="$(tar -tJf "$tmp/sc.tar.xz" 2>/dev/null | awk -F/ '/(^|\/)shellcheck$/{print $0; exit}')"
        if [ -n "$file" ] && [ -f "$tmp/$file" ]; then
          $INSTALL "$tmp/$file" "$BIN_DIR/shellcheck" && return
        fi
        # Fallback: search extracted tree
        file="$(find "$tmp" -type f -name shellcheck -perm -111 | head -n1)"
        if [ -n "$file" ]; then $INSTALL "$file" "$BIN_DIR/shellcheck" && return; fi
      fi
    fi
  fi
  # Fallback to apt if GitHub binary not available
  if have apt-get; then sudo apt-get update && sudo apt-get install -y shellcheck; return; fi
}

install_fx() {
  # Prefer Go implementation
  if command -v go >/dev/null 2>&1; then
    GO111MODULE=on go install github.com/antonmedv/fx@latest && $INSTALL "$(go_bin_path)/fx" "$BIN_DIR/fx" && return
  fi
  # Fallback
  if have brew; then brew install fx; return; fi
}

install_glab() {
  if have brew; then brew install glab; return; fi
  # Try GitHub release binary (profclems/glab)
  local tmp tag ver url name file AUTH
  tmp="$(mktemp -d)"
  if [ -n "${GITHUB_TOKEN:-}" ]; then AUTH=( -H "Authorization: Bearer ${GITHUB_TOKEN}" ); else AUTH=(); fi
  tag="$(curl -fsSIL ${AUTH[@]} -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' https://github.com/profclems/glab/releases/latest | awk -F'/' '{print $NF}')"
  if [ -n "$tag" ]; then
    ver="${tag#v}"
    # Try a set of common asset name patterns produced by goreleaser
    for name in \
      "glab_${ver}_Linux_x86_64.tar.gz" \
      "glab_${ver}_linux_x86_64.tar.gz" \
      "glab_${ver}_linux_amd64.tar.gz" \
      "glab_${ver}_Linux_amd64.tar.gz" \
      "glab_${ver}_Linux_arm64.tar.gz" \
      "glab_${ver}_linux_arm64.tar.gz" \
      "glab_${ver}_Linux_${ARCH}.tar.gz" \
      "glab_${ver}_linux_${ARCH}.tar.gz"; do
      url="https://github.com/profclems/glab/releases/download/${tag}/${name}"
      if curl -fsSL ${AUTH[@]} -H "User-Agent: cli-audit" "$url" -o "$tmp/glab.tgz"; then
        if tar -C "$tmp" -xzf "$tmp/glab.tgz" >/dev/null 2>&1; then
          # Look for an extracted 'glab' binary
          file="$(tar -tzf "$tmp/glab.tgz" 2>/dev/null | awk -F/ '/(^|\/)glab$/{print $0; exit}')"
          if [ -n "$file" ] && [ -f "$tmp/$file" ]; then
            $INSTALL "$tmp/$file" "$BIN_DIR/glab" && return
          fi
          file="$(find "$tmp" -type f -name glab -perm -111 | head -n1)"
          if [ -n "$file" ]; then
            $INSTALL "$file" "$BIN_DIR/glab" && return
          fi
        fi
      fi
    done
  fi
  # Fallback: install via Go if available
  if command -v go >/dev/null 2>&1; then
    # Prefer the canonical module path if present
    GO111MODULE=on go install gitlab.com/gitlab-org/cli/cmd/glab@latest 2>/dev/null || GO111MODULE=on go install github.com/profclems/glab@latest || true
    if [ -x "$(go_bin_path)/glab" ]; then
      $INSTALL "$(go_bin_path)/glab" "$BIN_DIR/glab" && return
    fi
  fi
}

install_just() {
  if have brew; then
    if have just; then brew upgrade just || brew install just; else brew install just; fi
    return
  fi
  if have cargo; then cargo install just; return; fi
}

install_core_tools() {
  install_fd
  install_fzf
  install_rg
  install_jq
  install_yq
  install_bat
  install_delta
  install_just
}

update_core_tools() {
  if have brew; then brew upgrade fd fzf ripgrep jq yq bat git-delta just || true; fi
  # On apt systems, try to upgrade via apt-get if packages exist
  if have apt-get; then sudo apt-get update || true; sudo apt-get install -y --only-upgrade fzf ripgrep jq yq bat || true; fi
}

reconcile_one() {
  local t="$1"
  local before after path
  before="$(get_version "$t" || true)"
  case "$t" in
    fd)
      sudo apt-get remove -y fd-find >/dev/null 2>&1 || true
      install_fd
      ;;
    ripgrep)
      sudo apt-get remove -y ripgrep >/dev/null 2>&1 || true
      install_rg
      ;;
    jq)
      sudo apt-get remove -y jq >/dev/null 2>&1 || true
      install_jq
      ;;
    yq)
      sudo apt-get remove -y yq >/dev/null 2>&1 || true
      $RM "/usr/local/bin/yq" >/dev/null 2>&1 || true
      rm -f "$HOME/.local/bin/yq" >/dev/null 2>&1 || true
      FORCE=1 install_yq
      ;;
    bat)
      sudo apt-get remove -y bat >/dev/null 2>&1 || true
      install_bat
      ;;
    delta)
      sudo apt-get remove -y git-delta >/dev/null 2>&1 || true
      install_delta
      ;;
    just)
      sudo apt-get remove -y just >/dev/null 2>&1 || true
      install_just
      ;;
    fzf)
      sudo apt-get remove -y fzf >/dev/null 2>&1 || true
      install_fzf
      ;;
    curlie)
      sudo apt-get remove -y curlie >/dev/null 2>&1 || true
      rm -f "/usr/local/bin/curlie" "$HOME/.local/bin/curlie" "$(go_bin_path)/curlie" >/dev/null 2>&1 || true
      install_curlie
      ;;
    dive)
      sudo apt-get remove -y dive >/dev/null 2>&1 || true
      install_dive
      ;;
    trivy)
      sudo apt-get remove -y trivy >/dev/null 2>&1 || true
      install_trivy
      ;;
    gitleaks)
      sudo apt-get remove -y gitleaks >/dev/null 2>&1 || true
      install_gitleaks
      ;;
    git-absorb)
      install_git_absorb
      ;;
    git-branchless)
      install_git_branchless
      ;;
    eslint)
      install_eslint
      ;;
    prettier)
      install_prettier
      ;;
    shfmt)
      install_shfmt
      ;;
    shellcheck)
      sudo apt-get remove -y shellcheck >/dev/null 2>&1 || true
      $RM "/usr/local/bin/shellcheck" >/dev/null 2>&1 || true
      install_shellcheck
      ;;
    fx)
      # Remove Node variant if present, then install Go variant
      ensure_nvm_loaded || true
      if command -v npm >/dev/null 2>&1; then
        env -u PREFIX npm uninstall -g fx >/dev/null 2>&1 || true
        env -u PREFIX npm uninstall -g --prefix "$HOME/.local" fx >/dev/null 2>&1 || true
        node_root="$(npm root -g 2>/dev/null || true)"; if [ -n "$node_root" ]; then rm -rf "$node_root/fx" >/dev/null 2>&1 || true; fi
      fi
      rm -f "$HOME/.local/bin/fx" >/dev/null 2>&1 || true
      install_fx
      ;;
    glab)
      install_glab
      ;;
    ctags)
      # Record baseline presence of distro ctags packages
      base_ctags_pkg=0; base_exuberant_pkg=0; base_universal_pkg=0
      if have apt-get; then
        dpkg -s ctags >/dev/null 2>&1 && base_ctags_pkg=1 || true
        dpkg -s exuberant-ctags >/dev/null 2>&1 && base_exuberant_pkg=1 || true
        dpkg -s universal-ctags >/dev/null 2>&1 && base_universal_pkg=1 || true
      fi
      install_ctags
      # If we successfully installed to /usr/local and any distro ctags packages were not present before
      # but are present now (unlikely unless installed earlier in this run), remove them to avoid confusion.
      if have apt-get; then
        cur_ctags_pkg=0; cur_exuberant_pkg=0; cur_universal_pkg=0
        dpkg -s ctags >/dev/null 2>&1 && cur_ctags_pkg=1 || true
        dpkg -s exuberant-ctags >/dev/null 2>&1 && cur_exuberant_pkg=1 || true
        dpkg -s universal-ctags >/dev/null 2>&1 && cur_universal_pkg=1 || true
        ctags_path="$(command -v ctags 2>/dev/null || true)"
        if [ "$ctags_path" = "/usr/local/bin/ctags" ]; then
          if [ "$base_ctags_pkg" -eq 0 ] && [ "$cur_ctags_pkg" -eq 1 ]; then sudo apt-get remove -y ctags >/dev/null 2>&1 || true; fi
          if [ "$base_exuberant_pkg" -eq 0 ] && [ "$cur_exuberant_pkg" -eq 1 ]; then sudo apt-get remove -y exuberant-ctags >/dev/null 2>&1 || true; fi
          if [ "$base_universal_pkg" -eq 0 ] && [ "$cur_universal_pkg" -eq 1 ]; then sudo apt-get remove -y universal-ctags >/dev/null 2>&1 || true; fi
        fi
      fi
      ;;
    entr)
      sudo apt-get remove -y entr >/dev/null 2>&1 || true
      install_entr
      ;;
    parallel)
      sudo apt-get remove -y parallel >/dev/null 2>&1 || true
      install_parallel
      ;;
    ast-grep)
      rm -f "/usr/local/bin/ast-grep" "$HOME/.local/bin/ast-grep" "$(go_bin_path)/ast-grep" >/dev/null 2>&1 || true
      install_ast_grep
      ;;
    direnv)
      sudo apt-get remove -y direnv >/dev/null 2>&1 || true
      install_direnv
      ;;
    git)
      install_git
      ;;
    gh)
      install_gh
      ;;
    *) echo "Unknown tool: $t" ;;
  esac
  path="$(command -v "$t" 2>/dev/null || true)"
  after="$(get_version "$t" || true)"
  printf "[%s] before: %s\n" "$t" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$t" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$t" "$path"; fi
}

uninstall_core_tools() {
  if have brew; then brew uninstall -f fd fzf ripgrep jq yq bat git-delta just || true; fi
  apt_remove_if_present fd-find fzf ripgrep jq yq bat || true
}

case "$ACTION" in
  install) install_core_tools ;;
  update) update_core_tools ;;
  uninstall) uninstall_core_tools ;;
  reconcile)
    if [ -n "$ONLY_TOOL" ]; then
      reconcile_one "$ONLY_TOOL"
    else
      for t in fd fzf ripgrep jq yq bat delta just; do reconcile_one "$t"; done
    fi
    ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "core: $ACTION complete (or attempted). You may need to add $BIN_DIR to PATH." ;;
esac


