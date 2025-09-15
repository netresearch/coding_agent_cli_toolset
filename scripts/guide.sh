#!/usr/bin/env bash
set -euo pipefail
# Avoid aborting on SIGPIPE if any downstream reader closes early
trap '' PIPE

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VERBOSE="${VERBOSE:-0}"
OFFLINE="${OFFLINE:-0}"

CLI="${PYTHON:-python3}"

run_audit() {
  (cd "$ROOT" && CLI_AUDIT_OFFLINE="$OFFLINE" CLI_AUDIT_LINKS=0 CLI_AUDIT_EMOJI=0 CLI_AUDIT_TIMEOUT_SECONDS="${CLI_AUDIT_TIMEOUT_SECONDS:-3}" "$CLI" cli_audit.py)
}

get_field() {
  # usage: get_field TOOL field_index
  # fields: 1:state 2:tool 3:installed 4:installed_method 5:latest 6:upstream_method
  local tool="$1" idx="$2"
  awk -F'[|]' -v t="$tool" -v i="$idx" 'NR>1 && $2==t {gsub(/^ +| +$/,"",$i); print $i; exit}' <<< "$AUDIT_OUTPUT"
}

prompt_action() {
  local title="$1" current="$2" method="$3" latest="$4" planned="$5" tool="$6"
  printf "\n"
  printf "==> %s\n" "$title"
  printf "    installed: %s via %s\n" "${current:-<none>}" "${method:-unknown}"
  printf "    target:    %s via %s\n" "${latest:-<unknown>}" "${planned:-unknown}"
  # Preview command to be executed
  case "$tool" in
    rust)        printf "    will run: scripts/install_rust.sh reconcile\n" ;;
    core)        printf "    will run: scripts/install_core.sh update\n" ;;
    python)      printf "    will run: scripts/install_python.sh update\n" ;;
    pip|pipx|poetry|httpie|semgrep)
                  printf "    will run: uv tool install --force --upgrade %s\n" "$tool" ;;
    node)        printf "    will run: scripts/install_node.sh reconcile\n" ;;
    go)          printf "    will run: scripts/install_go.sh\n" ;;
    docker)      printf "    will run: scripts/install_docker.sh\n" ;;
    docker-compose) printf "    will run: echo 'Ensure Docker is up to date (Compose v2 plugin)'\n" ;;
    aws)         printf "    will run: scripts/install_aws.sh\n" ;;
    kubectl)     printf "    will run: scripts/install_kubectl.sh update\n" ;;
    terraform)   printf "    will run: scripts/install_terraform.sh\n" ;;
    ansible)     printf "    will run: scripts/install_ansible.sh update\n" ;;
    *)           printf "    will run: scripts/install_core.sh reconcile %s\n" "$tool" ;;
  esac
  local ans
  # Read from the real TTY to avoid broken pipes when stdout/stderr are piped
  if [ -t 0 ]; then
    read -r -p "Install/update? [y/N] " ans || true
  else
    # Fallback: read from /dev/tty if available
    if [ -r /dev/tty ]; then
      read -r -p "Install/update? [y/N] " ans </dev/tty || true
    else
      ans=""
    fi
  fi
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    return 0
  fi
  return 1
}

ensure_perms() {
  chmod +x "$ROOT"/scripts/*.sh || true
  chmod +x "$ROOT"/scripts/lib/*.sh || true
}

ensure_perms

echo "Gathering current tool status... (offline=$OFFLINE, timeout=${CLI_AUDIT_TIMEOUT_SECONDS:-3}s)"
# Capture audit output safely; avoid broken pipe noises when downstream prompts stop reading
AUDIT_OUTPUT="$(run_audit || true)"
# Also capture JSON using cached latests to avoid extra network calls
AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_OFFLINE="$OFFLINE" "$CLI" cli_audit.py 2>/dev/null || true)"
if [ "$VERBOSE" = "1" ]; then
  # Pretty print the audit output for context
  printf "%s\n" "$AUDIT_OUTPUT" | "$CLI" smart_column.py -s '|' -t --right 3,5 --header || printf "%s\n" "$AUDIT_OUTPUT"
fi

# Helpers to read JSON and render links
json_field() {
  # usage: json_field TOOL KEY
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "")
data = data.strip()
tool = sys.argv[1]
key = sys.argv[2]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            v = item.get(key, "")
            if v is None:
                v = ""
            print(v)
            break
except Exception:
    print("")
PY
}

json_bool() {
  # usage: json_bool TOOL KEY   -> prints 1 if true, else empty
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool = sys.argv[1]
key = sys.argv[2]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            v = item.get(key)
            if isinstance(v, bool) and v:
                print("1")
            break
except Exception:
    pass
PY
}

osc8() {
  local url="$1"; shift
  local text="$*"
  if [ -n "$url" ]; then
    printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$url" "$text"
  else
    printf '%s' "$text"
  fi
}

# Rust first (for cargo-based tools) - use JSON for accuracy
RUST_ICON="$(json_field rust state_icon)"
RUST_INSTALLED="$(json_field rust installed)"
RUST_METHOD="$(json_field rust installed_method)"
RUST_LATEST="$(json_field rust latest_upstream)"
RUST_URL="$(json_field rust latest_url)"
if [ -n "$(json_bool rust is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$RUST_ICON" "Rust (cargo)"
  printf "    installed: %s via %s\n" "${RUST_INSTALLED:-<none>}" "${RUST_METHOD:-unknown}"
  printf "    target:    %s via %s\n" "$(osc8 "$RUST_URL" "${RUST_LATEST:-<unknown>}")" "$(json_field rust upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${RUST_ICON} Rust (cargo)" "$RUST_INSTALLED" "$RUST_METHOD" "$(osc8 "$RUST_URL" "$RUST_LATEST")" "$(json_field rust upstream_method)" rust; then
    "$ROOT"/scripts/install_rust.sh reconcile
  fi
fi

# UV (ensure official binary) + Python stack (before Node/core tools)
UV_ICON="$(json_field uv state_icon)"
UV_CURR="$(json_field uv installed)"
UV_LATEST="$(json_field uv latest_upstream)"
UV_URL="$(json_field uv latest_url)"
if [ -n "$(json_bool uv is_up_to_date)" ] && [ -n "$UV_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$UV_ICON" "uv"
  printf "    installed: %s via %s\n" "${UV_CURR:-<none>}" "$(json_field uv installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$UV_URL" "${UV_LATEST:-<unknown>}")" "$(json_field uv upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${UV_ICON} uv" "$UV_CURR" "$(json_field uv installed_method)" "$(osc8 "$UV_URL" "$UV_LATEST")" "$(json_field uv upstream_method)" core; then
    "$ROOT"/scripts/install_uv.sh reconcile
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
  fi
fi

# Python stack (after ensuring uv)
PY_ICON="$(json_field python state_icon)"
PY_CURR="$(json_field python installed)"
PY_LATEST="$(json_field python latest_upstream)"
PY_URL="$(json_field python latest_url)"
if [ -n "$(json_bool python is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$PY_ICON" "Python stack"
  printf "    installed: %s via %s\n" "${PY_CURR:-<none>}" "$(json_field python installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$PY_URL" "${PY_LATEST:-<unknown>}")" "$(json_field python upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${PY_ICON} Python stack" "$PY_CURR" "$(json_field python installed_method)" "$(osc8 "$PY_URL" "$PY_LATEST")" "$(json_field python upstream_method)" python; then
    UV_PYTHON_SPEC="$PY_LATEST" "$ROOT"/scripts/install_python.sh update
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
  fi
fi

# Node stack (Node + package managers)
NODE_ICON="$(json_field node state_icon)"
NODE_CURR="$(json_field node installed)"
NODE_LATEST="$(json_field node latest_upstream)"
NODE_URL="$(json_field node latest_url)"
# Treat stack as up-to-date only if node, npm, pnpm, and yarn are all up-to-date
NODE_ALL_OK=""
if [ -n "$(json_bool node is_up_to_date)" ] && [ -n "$(json_bool npm is_up_to_date)" ] && [ -n "$(json_bool pnpm is_up_to_date)" ] && [ -n "$(json_bool yarn is_up_to_date)" ]; then
  NODE_ALL_OK="1"
fi
if [ -n "$NODE_ALL_OK" ]; then
  printf "\n"; printf "==> %s %s\n" "$NODE_ICON" "Node.js stack"; printf "    installed: %s via %s\n" "${NODE_CURR:-<none>}" "$(json_field node installed_method)"; printf "    target:    %s via %s\n" "$(osc8 "$NODE_URL" "${NODE_LATEST:-<unknown>}")" "$(json_field node upstream_method)"; printf "    up-to-date; skipping.\n"
else
  if prompt_action "${NODE_ICON} Node.js stack" "$NODE_CURR" "$(json_field node installed_method)" "$(osc8 "$NODE_URL" "$NODE_LATEST")" "$(json_field node upstream_method)" node; then
    "$ROOT"/scripts/install_node.sh reconcile
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
  fi
fi

# Always offer explicit package manager updates, regardless of Node prompt choice
if prompt_action "$(json_field npm state_icon) npm (global)" "$(json_field npm installed)" "$(json_field npm installed_method)" "$(osc8 "$(json_field npm latest_url)" "$(json_field npm latest_upstream)")" "$(json_field npm upstream_method)" npm; then
  corepack enable >/dev/null 2>&1 || true
  npm install -g npm@latest >/dev/null 2>&1 || true
  AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
fi
if prompt_action "$(json_field pnpm state_icon) pnpm" "$(json_field pnpm installed)" "$(json_field pnpm installed_method)" "$(osc8 "$(json_field pnpm latest_url)" "$(json_field pnpm latest_upstream)")" "$(json_field pnpm upstream_method)" pnpm; then
  corepack prepare pnpm@latest --activate >/dev/null 2>&1 || npm install -g pnpm@latest >/dev/null 2>&1 || true
  AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
fi
if prompt_action "$(json_field yarn state_icon) yarn" "$(json_field yarn installed)" "$(json_field yarn installed_method)" "$(osc8 "$(json_field yarn latest_url)" "$(json_field yarn latest_upstream)")" "$(json_field yarn upstream_method)" yarn; then
  # Prefer stable tag for Yarn (Berry)
  corepack prepare yarn@stable --activate >/dev/null 2>&1 || npm install -g yarn@latest >/dev/null 2>&1 || true
  AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
fi

# Go stack – show sanitized version and planned source (before core tools that use go)
GO_ICON="$(json_field go state_icon)"
GO_CURR_RAW="$(command -v go >/dev/null 2>&1 && go version 2>/dev/null | awk '{print $3}' || echo)"
GO_CURR="${GO_CURR_RAW#go}"
GO_LATE="$(json_field go latest_upstream)"
GO_URL="$(json_field go latest_url)"
if [ -n "${GO_CURR}" ]; then GO_METHOD="go"; else GO_METHOD="none"; fi
if [ -n "$(json_bool go is_up_to_date)" ]; then
  printf "\n"; printf "==> %s %s\n" "$GO_ICON" "Go toolchain"; printf "    installed: %s via %s\n" "$GO_CURR" "$GO_METHOD"; printf "    target:    %s via %s\n" "$(osc8 "$GO_URL" "${GO_LATE:-<unknown>}")" "brew"; printf "    up-to-date; skipping.\n"
else
  if prompt_action "${GO_ICON} Go toolchain" "$GO_CURR" "$GO_METHOD" "$(osc8 "$GO_URL" "$GO_LATE")" "brew" go; then
    "$ROOT"/scripts/install_go.sh
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
  fi
fi

# Prefer uv for Python CLI tools: offer migration from pipx/user when detected
if command -v uv >/dev/null 2>&1 || "$ROOT"/scripts/install_uv.sh reconcile >/dev/null 2>&1; then
  # Include all Python console CLIs we track (expandable). ansible is handled separately below.
  for t in pip pipx poetry httpie pre-commit bandit semgrep black isort flake8; do
    METHOD="$(json_field "$t" installed_method)"
    if [ -n "$METHOD" ] && [ -z "$(json_bool "$t" is_up_to_date)" ]; then
      : # keep normal outdated prompts elsewhere
    fi
    # Migrate only when pipx is the current method
    if [ -n "$METHOD" ] && printf "%s" "$METHOD" | grep -Eqi "pipx|pip/user|pip"; then
      ICON="$(json_field "$t" state_icon)"
      CURR="$(json_field "$t" installed)"
      LATE="$(json_field "$t" latest_upstream)"
      URL="$(json_field "$t" latest_url)"
      TITLE="$ICON $t (migrate to uv tool)"
      if prompt_action "$TITLE" "$CURR" "$METHOD" "$(osc8 "$URL" "$LATE")" "uv tool" "$t"; then
        # Install via uv tool, then remove pipx version to avoid shim conflicts
        uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then pipx uninstall "$t" >/dev/null 2>&1 || true; fi
        # Remove user pip scripts that might shadow uv tools
        rm -f "$HOME/.local/bin/$t" >/dev/null 2>&1 || true
        AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
      fi
    fi
  done
fi

# Core tools (fd, fzf, rg, jq, yq, bat, delta, just, and npm/cargo/go tools)
CORE_TOOLS=(fd fzf ripgrep jq yq bat delta just curlie dive trivy gitleaks git-absorb git-branchless eslint prettier shfmt shellcheck fx glab ctags entr parallel ast-grep direnv git gh)
for t in "${CORE_TOOLS[@]}"; do
  ICON="$(json_field "$t" state_icon)"
  CURR="$(json_field "$t" installed)"
  LATE="$(json_field "$t" latest_upstream)"
  URL="$(json_field "$t" latest_url)"
  if [ -n "$(json_bool "$t" is_up_to_date)" ]; then
    printf "\n"; printf "==> %s %s\n" "$ICON" "$t"; printf "    installed: %s via %s\n" "${CURR:-<none>}" "$(json_field "$t" installed_method)"; printf "    target:    %s via %s\n" "$(osc8 "$URL" "${LATE:-<unknown>}")" "$(json_field "$t" upstream_method)"; printf "    up-to-date; skipping.\n"; continue
  fi
  if prompt_action "${ICON} $t" "$CURR" "$(json_field "$t" installed_method)" "$(osc8 "$URL" "$LATE")" "$(json_field "$t" upstream_method)" "$t"; then
    "$ROOT"/scripts/install_core.sh reconcile "$t"
    # Re-audit the single tool to reflect updated status inline
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
  fi
done

# Python utilities (managed via pipx): prompt individually if outdated/missing
for t in pip pipx poetry httpie semgrep black; do
  if [ -z "$(json_bool "$t" is_up_to_date)" ]; then
    ICON="$(json_field "$t" state_icon)"
    CURR="$(json_field "$t" installed)"
    LATE="$(json_field "$t" latest_upstream)"
    URL="$(json_field "$t" latest_url)"
    if prompt_action "${ICON} $t" "$CURR" "$(json_field "$t" installed_method)" "$(osc8 "$URL" "$LATE")" "$(json_field "$t" upstream_method)" "$t"; then
      if command -v uv >/dev/null 2>&1; then
        uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
      else
        "$ROOT"/scripts/install_uv.sh reconcile || true
        if command -v uv >/dev/null 2>&1; then
          uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
        else
          if command -v pipx >/dev/null 2>&1; then
            pipx upgrade "$t" >/dev/null 2>&1 || pipx install "$t" >/dev/null 2>&1 || true
          else
            if [ "$t" = pip ]; then
              python3 -m pip install --user -U pip >/dev/null 2>&1 || true
            elif [ "$t" = pipx ]; then
              python3 -m pip install --user -U pipx >/dev/null 2>&1 || true
            else
              python3 -m pip install --user -U "$t" >/dev/null 2>&1 || true
            fi
          fi
        fi
      fi
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" cli_audit.py 2>/dev/null || true)"
    fi
  fi
done

# Docker
DK_ICON="$(json_field docker state_icon)"
DK_CURR="$(json_field docker installed)"
DK_LATEST="$(json_field docker latest_upstream)"
DK_URL="$(json_field docker latest_url)"
if [ -n "$(json_bool docker is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$DK_ICON" "Docker Engine"
  printf "    installed: %s via %s\n" "${DK_CURR:-<none>}" "$(json_field docker installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$DK_URL" "${DK_LATEST:-<unknown>}")" "$(json_field docker upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${DK_ICON} Docker Engine" "$DK_CURR" "$(json_field docker installed_method)" "$(osc8 "$DK_URL" "$DK_LATEST")" "$(json_field docker upstream_method)" docker; then
    "$ROOT"/scripts/install_docker.sh
  fi
fi

# Docker Compose (plugin)
DC_ICON="$(json_field docker-compose state_icon)"
DC_CURR="$(json_field docker-compose installed)"
DC_LATEST="$(json_field docker-compose latest_upstream)"
DC_URL="$(json_field docker-compose latest_url)"
if [ -n "$(json_bool docker-compose is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$DC_ICON" "Docker Compose"
  printf "    installed: %s via %s\n" "${DC_CURR:-<none>}" "$(json_field docker-compose installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$DC_URL" "${DC_LATEST:-<unknown>}")" "$(json_field docker-compose upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${DC_ICON} Docker Compose" "$DC_CURR" "$(json_field docker-compose installed_method)" "$(osc8 "$DC_URL" "$DC_LATEST")" "$(json_field docker-compose upstream_method)" docker-compose; then
    echo "Note: Docker Compose v2 is bundled as Docker plugin; ensure Docker is up to date."
  fi
fi

# AWS CLI (ask if missing or outdated)
AWS_ICON="$(json_field aws state_icon)"
AWS_CURR="$(json_field aws installed)"
AWS_LATEST="$(json_field aws latest_upstream)"
AWS_URL="$(json_field aws latest_url)"
if [ -n "$(json_bool aws is_up_to_date)" ] && [ -n "$AWS_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$AWS_ICON" "AWS CLI"
  printf "    installed: %s via %s\n" "${AWS_CURR:-<none>}" "$(json_field aws installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$AWS_URL" "${AWS_LATEST:-<unknown>}")" "$(json_field aws upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${AWS_ICON} AWS CLI" "$AWS_CURR" "$(json_field aws installed_method)" "$(osc8 "$AWS_URL" "$AWS_LATEST")" "$(json_field aws upstream_method)" aws; then
    "$ROOT"/scripts/install_aws.sh
  fi
fi

# kubectl
K8S_ICON="$(json_field kubectl state_icon)"
K8S_CURR="$(json_field kubectl installed)"
K8S_LATEST="$(json_field kubectl latest_upstream)"
K8S_URL="$(json_field kubectl latest_url)"
if [ -n "$(json_bool kubectl is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$K8S_ICON" "kubectl"
  printf "    installed: %s via %s\n" "${K8S_CURR:-<none>}" "$(json_field kubectl installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$K8S_URL" "${K8S_LATEST:-<unknown>}")" "$(json_field kubectl upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${K8S_ICON} kubectl" "$K8S_CURR" "$(json_field kubectl installed_method)" "$(osc8 "$K8S_URL" "$K8S_LATEST")" "$(json_field kubectl upstream_method)" kubectl; then
    "$ROOT"/scripts/install_kubectl.sh update
  fi
fi

# Terraform
TF_ICON="$(json_field terraform state_icon)"
TF_CURR="$(json_field terraform installed)"
TF_LATEST="$(json_field terraform latest_upstream)"
TF_URL="$(json_field terraform latest_url)"
if [ -n "$(json_bool terraform is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$TF_ICON" "Terraform"
  printf "    installed: %s via %s\n" "${TF_CURR:-<none>}" "$(json_field terraform installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$TF_URL" "${TF_LATEST:-<unknown>}")" "$(json_field terraform upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${TF_ICON} Terraform" "$TF_CURR" "$(json_field terraform installed_method)" "$(osc8 "$TF_URL" "$TF_LATEST")" "$(json_field terraform upstream_method)" terraform; then
    "$ROOT"/scripts/install_terraform.sh
  fi
fi

# Ansible
ANS_ICON="$(json_field ansible state_icon)"
ANS_CURR="$(json_field ansible installed)"
ANS_LATEST="$(json_field ansible latest_upstream)"
ANS_URL="$(json_field ansible latest_url)"
if [ -n "$(json_bool ansible is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$ANS_ICON" "Ansible"
  printf "    installed: %s via %s\n" "${ANS_CURR:-<none>}" "$(json_field ansible installed_method)"
  printf "    target:    %s via %s\n" "$(osc8 "$ANS_URL" "${ANS_LATEST:-<unknown>}")" "$(json_field ansible upstream_method)"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${ANS_ICON} Ansible" "$ANS_CURR" "$(json_field ansible installed_method)" "$(osc8 "$ANS_URL" "$ANS_LATEST")" "$(json_field ansible upstream_method)" ansible; then
    "$ROOT"/scripts/install_ansible.sh update
  fi
fi

echo
echo "All done. Re-run: make audit"



