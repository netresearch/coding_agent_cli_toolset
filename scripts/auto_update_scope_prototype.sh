#!/usr/bin/env bash
# Prototype: Package Manager Scope Detection System
# This is a working proof-of-concept for scope distinction (system/user/project)

set -euo pipefail

# ============================================================================
# Core Scope Detection Functions
# ============================================================================

get_manager_scope() {
  local mgr="$1"
  local scopes=""

  case "$mgr" in
    apt)
      # APT is always system-level
      scopes="system"
      ;;

    brew)
      # Detect Homebrew installation type by checking installation directory
      if [ -d "/home/linuxbrew" ] || [ -d "/opt/homebrew" ]; then
        scopes="system"
      elif [ -d "$HOME/.linuxbrew" ] || [ -d "$HOME/.brew" ]; then
        scopes="user"
      else
        # Fallback: check brew --prefix ownership
        local brew_prefix="$(brew --prefix 2>/dev/null || echo "")"
        if [ -n "$brew_prefix" ]; then
          if [[ "$brew_prefix" == "$HOME"* ]]; then
            scopes="user"
          else
            scopes="system"
          fi
        fi
      fi
      ;;

    snap)
      # Snap is always system-level
      scopes="system"
      ;;

    flatpak)
      # Flatpak supports both system and user scopes
      local system_count user_count
      system_count="$(flatpak list --system --app 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"
      user_count="$(flatpak list --user --app 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"

      if [ "${system_count:-0}" -gt 0 ] && [ "${user_count:-0}" -gt 0 ]; then
        scopes="system,user"
      elif [ "${system_count:-0}" -gt 0 ]; then
        scopes="system"
      elif [ "${user_count:-0}" -gt 0 ]; then
        scopes="user"
      fi
      ;;

    cargo)
      # Cargo is always user-scoped (installs to ~/.cargo)
      scopes="user"
      ;;

    rustup)
      # Rustup is always user-scoped (manages user toolchains)
      scopes="user"
      ;;

    uv)
      # UV tools are user-scoped, but can manage project venvs
      scopes="user"
      if [ -d "./.venv" ]; then
        scopes="user,project"
      fi
      ;;

    pipx)
      # Pipx is always user-scoped
      scopes="user"
      ;;

    pip)
      # PIP supports user and project (venv) scopes
      scopes="user"
      # Check for active venv or project venv directory
      if [ -n "${VIRTUAL_ENV:-}" ] || [ -d "./.venv" ] || [ -d "./venv" ]; then
        scopes="user,project"
      fi
      ;;

    npm)
      # NPM supports all three scopes
      local npm_prefix="$(npm config get prefix 2>/dev/null || echo "")"

      if [ -n "$npm_prefix" ]; then
        if [[ "$npm_prefix" == "$HOME"* ]]; then
          scopes="user"
        else
          scopes="system"
        fi
      fi

      # Check for project scope
      if [ -f "./package.json" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    pnpm)
      # PNPM similar to NPM
      local pnpm_prefix="$(pnpm config get prefix 2>/dev/null || echo "")"

      if [ -n "$pnpm_prefix" ]; then
        if [[ "$pnpm_prefix" == "$HOME"* ]]; then
          scopes="user"
        else
          scopes="system"
        fi
      fi

      if [ -f "./package.json" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    yarn)
      # Yarn similar to NPM
      local yarn_prefix="$(yarn global dir 2>/dev/null | head -n1 || echo "")"

      if [ -n "$yarn_prefix" ]; then
        if [[ "$yarn_prefix" == "$HOME"* ]]; then
          scopes="user"
        else
          scopes="system"
        fi
      fi

      if [ -f "./package.json" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    go)
      # Go is typically user-scoped (GOPATH/GOBIN in home directory)
      scopes="user"
      ;;

    gem)
      # RubyGems can be system or user
      local gem_dir="$(gem environment gemdir 2>/dev/null || echo "")"

      if [ -n "$gem_dir" ]; then
        if [[ "$gem_dir" == "$HOME"* ]]; then
          scopes="user"
        else
          scopes="system"
        fi
      fi

      # Check for project scope (Gemfile)
      if [ -f "./Gemfile" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    composer)
      # Composer: global (user) + project
      scopes="user"
      if [ -f "./composer.json" ]; then
        scopes="user,project"
      fi
      ;;

    poetry)
      # Poetry is project-only (manages project venvs)
      scopes="project"
      ;;

    conda)
      # Conda: can have base (system/user) + environments (user/project)
      local conda_prefix="${CONDA_PREFIX:-}"
      if [ -n "$conda_prefix" ]; then
        if [[ "$conda_prefix" == *"/base"* ]]; then
          scopes="system"
        else
          scopes="user"
        fi
      else
        scopes="user"
      fi

      # Check for environment.yml (project)
      if [ -f "./environment.yml" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    mamba)
      # Mamba same as conda
      local mamba_prefix="${MAMBA_PREFIX:-${CONDA_PREFIX:-}}"
      if [ -n "$mamba_prefix" ]; then
        if [[ "$mamba_prefix" == *"/base"* ]]; then
          scopes="system"
        else
          scopes="user"
        fi
      else
        scopes="user"
      fi

      if [ -f "./environment.yml" ]; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    bundler)
      # Bundler is project-only (Gemfile)
      if [ -f "./Gemfile" ]; then
        scopes="project"
      fi
      ;;

    jspm)
      # JSPM: global (user) + project
      scopes="user"
      if [ -f "./package.json" ]; then
        scopes="user,project"
      fi
      ;;

    nuget)
      # NuGet: global (system/user) + project
      if command -v nuget >/dev/null 2>&1; then
        scopes="system"
      elif command -v dotnet >/dev/null 2>&1; then
        scopes="user"
      fi

      if [ -f "./*.csproj" ] 2>/dev/null || [ -f "./*.sln" ] 2>/dev/null; then
        [ -n "$scopes" ] && scopes="$scopes,project" || scopes="project"
      fi
      ;;

    gcloud)
      # Google Cloud SDK is typically user-scoped
      scopes="user"
      ;;

    az)
      # Azure CLI can be system or user
      if command -v apt-get >/dev/null 2>&1 && dpkg -l azure-cli >/dev/null 2>&1; then
        scopes="system"
      else
        scopes="user"
      fi
      ;;

    *)
      scopes="unknown"
      ;;
  esac

  echo "$scopes"
}

# ============================================================================
# Enhanced Stats with Scope-Specific Counts
# ============================================================================

get_scope_details() {
  local mgr="$1"
  local scope_details=""

  case "$mgr" in
    flatpak)
      local sys_count usr_count
      sys_count="$(flatpak list --system --app 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"
      usr_count="$(flatpak list --user --app 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"
      if [ "${sys_count:-0}" -gt 0 ] || [ "${usr_count:-0}" -gt 0 ]; then
        scope_details="sys:$sys_count,usr:$usr_count"
      fi
      ;;

    npm)
      local global_count="$(npm list -g --depth=0 2>/dev/null | grep -c '^[├└]' || echo "0")"
      scope_details="global:$global_count"

      if [ -f "./package.json" ]; then
        local project_count="$(npm list --depth=0 2>/dev/null | grep -c '^[├└]' || echo "0")"
        scope_details="$scope_details,project:$project_count"
      fi
      ;;

    pip)
      local user_count venv_count
      user_count="$(python3 -m pip list --user 2>/dev/null | tail -n +3 | wc -l | tr -d '[:space:]')"
      user_count="${user_count:-0}"
      scope_details="user:$user_count"

      if [ -n "${VIRTUAL_ENV:-}" ]; then
        venv_count="$(python3 -m pip list 2>/dev/null | tail -n +3 | wc -l | tr -d '[:space:]')"
        venv_count="${venv_count:-0}"
        scope_details="$scope_details,venv:$venv_count"
      fi
      ;;

    uv)
      local tools_count
      tools_count="$(uv tool list 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"
      scope_details="tools:$tools_count"
      ;;

    gem)
      local gem_count bundle_count
      gem_count="$(gem list --no-versions 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")"
      scope_details="gems:$gem_count"

      if [ -f "./Gemfile" ]; then
        bundle_count="$(bundle list 2>/dev/null | grep -c '^\s*\*' || echo "0")"
        scope_details="$scope_details,bundle:$bundle_count"
      fi
      ;;

    *)
      scope_details=""
      ;;
  esac

  echo "$scope_details"
}

get_manager_stats_with_scope() {
  local mgr="$1"
  local location version pkg_count scope scope_details

  # Detect location
  case "$mgr" in
    apt)
      location="$(command -v apt-get 2>/dev/null || echo "N/A")"
      version="$(apt-get --version 2>/dev/null | head -n1 | awk '{print $2}' || echo "unknown")"
      pkg_count="$(dpkg -l 2>/dev/null | grep '^ii' | wc -l || echo "0")"
      ;;
    brew)
      location="$(command -v brew 2>/dev/null || echo "N/A")"
      version="$(brew --version 2>/dev/null | head -n1 | awk '{print $2}' || echo "unknown")"
      pkg_count="$(brew list --formula 2>/dev/null | wc -l || echo "0")"
      ;;
    npm)
      location="$(command -v npm 2>/dev/null || echo "N/A")"
      version="$(npm --version 2>/dev/null || echo "unknown")"
      pkg_count="$(npm list -g --depth=0 2>/dev/null | grep -c '^[├└]' || echo "0")"
      ;;
    pip)
      location="$(command -v pip3 2>/dev/null || command -v pip 2>/dev/null || echo "N/A")"
      version="$(python3 -m pip --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(python3 -m pip list --user 2>/dev/null | tail -n +3 | wc -l || echo "0")"
      ;;
    cargo)
      location="$(command -v cargo 2>/dev/null || echo "N/A")"
      version="$(cargo --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(cargo install --list 2>/dev/null | grep -c '^[^ ]' || echo "0")"
      ;;
    flatpak)
      location="$(command -v flatpak 2>/dev/null || echo "N/A")"
      version="$(flatpak --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(flatpak list --app 2>/dev/null | wc -l || echo "0")"
      ;;
    *)
      location="unknown"
      version="unknown"
      pkg_count="0"
      ;;
  esac

  # Get scope
  scope="$(get_manager_scope "$mgr")"

  # Get scope-specific details
  scope_details="$(get_scope_details "$mgr")"

  # Build display string for packages
  local pkg_display="$pkg_count"
  if [ -n "$scope_details" ]; then
    pkg_display="$pkg_count ($scope_details)"
  fi

  printf "%s|%s|%s|%s|%s" "$location" "$version" "$pkg_display" "$scope" "$scope_details"
}

# ============================================================================
# Display Functions
# ============================================================================

show_scope_detection() {
  echo "Package Manager Scope Detection (Prototype)"
  echo "============================================"
  echo ""

  local managers=("apt" "brew" "npm" "pip" "cargo" "flatpak")

  echo "Detected Package Managers:"
  echo ""
  printf "%-12s %-8s %-12s %-20s %s\n" "MANAGER" "VERSION" "SCOPE" "PACKAGES" "LOCATION"
  printf "%-12s %-8s %-12s %-20s %s\n" "-------" "-------" "-----" "--------" "--------"

  for mgr in "${managers[@]}"; do
    # Check if manager exists
    if ! command -v "$mgr" >/dev/null 2>&1 && ! command -v "${mgr}-get" >/dev/null 2>&1 && ! command -v "apt-get" >/dev/null 2>&1; then
      continue
    fi

    local stats location version pkg_display scope scope_details
    stats="$(get_manager_stats_with_scope "$mgr")"
    IFS='|' read -r location version pkg_display scope scope_details <<< "$stats"

    printf "%-12s %-8s %-12s %-20s %s\n" "$mgr" "$version" "$scope" "$pkg_display" "$location"
  done
  echo ""
}

show_scope_analysis() {
  echo ""
  echo "Scope Analysis:"
  echo "==============="
  echo ""

  local managers=("apt" "brew" "npm" "pip" "cargo" "flatpak")

  for mgr in "${managers[@]}"; do
    if ! command -v "$mgr" >/dev/null 2>&1 && ! command -v "${mgr}-get" >/dev/null 2>&1 && ! command -v "apt-get" >/dev/null 2>&1; then
      continue
    fi

    local scope="$(get_manager_scope "$mgr")"
    local scope_details="$(get_scope_details "$mgr")"

    echo "[$mgr]"
    echo "  Scope: $scope"

    if [ -n "$scope_details" ]; then
      echo "  Details: $scope_details"
    fi

    # Provide context-specific insights
    if [[ "$scope" == *"project"* ]]; then
      echo "  ⚠️  Project scope detected - updates should be done manually in project context"
    fi

    if [[ "$scope" == *"system"* ]]; then
      echo "  🔒 System scope - updates may require sudo/administrator access"
    fi

    echo ""
  done
}

# ============================================================================
# Scope-Aware Update Example
# ============================================================================

update_npm_scope_aware() {
  echo "Example: Scope-Aware NPM Update"
  echo "================================"
  echo ""

  local scope="$(get_manager_scope "npm")"
  echo "Detected NPM scope: $scope"
  echo ""

  if [[ "$scope" == *"user"* ]] || [[ "$scope" == *"system"* ]]; then
    echo "Would update: Global NPM packages"
    echo "  Command: npm install -g npm@latest"
    echo "  Command: npm update -g"
  fi

  if [[ "$scope" == *"project"* ]]; then
    echo ""
    echo "📦 Project scope detected (./package.json)"
    echo "   To update project dependencies, run:"
    echo "   - npm update (update within version ranges)"
    echo "   - npm outdated (check for newer versions)"
    echo "   - npx npm-check-updates -u (update to latest)"
  fi
  echo ""
}

update_flatpak_scope_aware() {
  echo "Example: Scope-Aware Flatpak Update"
  echo "===================================="
  echo ""

  local scope="$(get_manager_scope "flatpak")"
  echo "Detected Flatpak scope: $scope"
  echo ""

  if [[ "$scope" == *"system"* ]]; then
    echo "Would update: System Flatpak applications"
    echo "  Command: flatpak update --system -y"
  fi

  if [[ "$scope" == *"user"* ]]; then
    echo "Would update: User Flatpak applications"
    echo "  Command: flatpak update --user -y"
  fi
  echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
  show_scope_detection
  show_scope_analysis

  echo "Scope-Aware Update Examples:"
  echo "============================"
  echo ""

  if command -v npm >/dev/null 2>&1; then
    update_npm_scope_aware
  fi

  if command -v flatpak >/dev/null 2>&1; then
    update_flatpak_scope_aware
  fi

  echo "Prototype Test Complete!"
  echo ""
  echo "Next Steps:"
  echo "  1. Review scope detection accuracy"
  echo "  2. Test edge cases (nvm, virtual envs, etc.)"
  echo "  3. Integrate into main auto_update.sh"
  echo "  4. Add --scope flag for selective updates"
}

main "$@"
