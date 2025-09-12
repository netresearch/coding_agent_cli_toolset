#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

before() { command -v docker >/dev/null 2>&1 && docker --version || true; }
after() { command -v docker >/dev/null 2>&1 && docker --version || true; }

# Reconcile to official script/apt on Debian/Ubuntu systems
if have apt-get; then
  echo "[docker] current: $(before)"
  # Remove legacy docker.io if present
  apt_purge_if_present docker.io docker-doc docker-compose podman-docker containerd runc || true
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
  echo "[docker] updated: $(after)"
  exit 0
fi

echo "Please install Docker following https://docs.docker.com/engine/install/"


