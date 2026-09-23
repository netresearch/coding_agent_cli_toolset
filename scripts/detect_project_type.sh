#!/usr/bin/env bash
# detect_project_type.sh - Detect project types from the files in a directory
# and name the catalog tools each type requires or recommends.
#
# Usage: detect_project_type.sh [text|json] [project_dir]
set -euo pipefail

FORMAT="${1:-text}"
PROJECT_DIR="${2:-.}"

detect_types() {
    local dir="$1"
    local -a types=()

    if [ -f "$dir/pyproject.toml" ] || [ -f "$dir/setup.py" ] || [ -f "$dir/requirements.txt" ] || [ -f "$dir/Pipfile" ]; then
        types+=("python")
    fi
    [ -f "$dir/package.json" ] && types+=("node")
    [ -f "$dir/Cargo.toml" ] && types+=("rust")
    [ -f "$dir/go.mod" ] && types+=("go")
    if [ -f "$dir/Gemfile" ] || [ -f "$dir/.ruby-version" ]; then
        types+=("ruby")
    fi
    if [ -f "$dir/composer.json" ] || [ -f "$dir/composer.lock" ] || compgen -G "$dir/*.php" >/dev/null; then
        types+=("php")
    fi
    if [ -f "$dir/Dockerfile" ] || [ -f "$dir/docker-compose.yml" ] || [ -f "$dir/docker-compose.yaml" ] \
        || [ -f "$dir/compose.yml" ] || [ -f "$dir/compose.yaml" ]; then
        types+=("docker")
    fi
    if compgen -G "$dir/*.tf" >/dev/null || [ -d "$dir/terraform" ]; then
        types+=("terraform")
    fi
    if [ -d "$dir/k8s" ] || compgen -G "$dir/*/deployment.yaml" >/dev/null; then
        types+=("kubernetes")
    fi
    if [ -f "$dir/ansible.cfg" ] || [ -d "$dir/playbooks" ]; then
        types+=("ansible")
    fi
    if [ -f "$dir/Makefile" ] || compgen -G "$dir/*.sh" >/dev/null; then
        types+=("shell")
    fi

    # ${a[@]+...}: an empty array is "unbound" under set -u before bash 4.4
    printf '%s\n' ${types[@]+"${types[@]}"}
}

# Catalog names (catalog/<name>.json), so each can be passed to install_tool.sh
required_tools() {
    case "$1" in
        python) echo "python uv" ;;
        node) echo "node npm" ;;
        rust) echo "rust" ;;
        go) echo "go" ;;
        ruby) echo "ruby" ;;
        php) echo "php composer" ;;
        docker) echo "docker compose" ;;
        terraform) echo "terraform" ;;
        kubernetes) echo "kubectl" ;;
        ansible) echo "ansible-core" ;;
        *) echo "" ;;
    esac
}

recommended_tools() {
    case "$1" in
        python) echo "ruff black" ;;
        node) echo "eslint prettier" ;;
        go) echo "golangci-lint" ;;
        docker) echo "dive trivy" ;;
        terraform) echo "tfsec trivy" ;;
        shell) echo "shellcheck shfmt" ;;
        *) echo "" ;;
    esac
}

detected="$(detect_types "$PROJECT_DIR")"

case "$FORMAT" in
    json)
        required="" recommended=""
        while IFS= read -r t; do
            [ -n "$t" ] || continue
            required+=" $(required_tools "$t")"
            recommended+=" $(recommended_tools "$t")"
        done <<<"$detected"
        jq -n \
            --arg types "$detected" --arg required "$required" --arg recommended "$recommended" \
            'def words: [splits("[[:space:]]+") | select(length > 0)] | unique;
             {project_types: ($types | [splits("\n") | select(length > 0)]),
              required_tools: ($required | words),
              recommended_tools: ($recommended | words)}'
        ;;
    text)
        if [ -z "$detected" ]; then
            echo "No specific project type detected"
            exit 0
        fi
        echo "Detected project types: $(tr '\n' ' ' <<<"$detected")"
        echo ""
        while IFS= read -r t; do
            req="$(required_tools "$t")"
            rec="$(recommended_tools "$t")"
            echo "[$t]"
            if [ -n "$req" ]; then echo "  Required: $req"; fi
            if [ -n "$rec" ]; then echo "  Recommended: $rec"; fi
        done <<<"$detected"
        ;;
    *)
        echo "Usage: $0 [text|json] [project_dir]" >&2
        exit 1
        ;;
esac
