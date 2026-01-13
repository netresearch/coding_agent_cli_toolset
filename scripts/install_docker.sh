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

  if is_wsl; then
    echo "[docker] WSL detected - installing Docker Engine (skipping 20s wait)..."
    echo "[docker] Note: Docker Desktop for Windows is also available."
    echo "[docker] See: https://docs.docker.com/desktop/wsl/"
    # Download script and remove the sleep to skip 20-second wait
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sed -i 's/sleep 20/sleep 0/' /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
    # Start service manually (no systemd in WSL)
    sudo service docker start || echo "[docker] Run 'sudo service docker start' to start Docker"
  else
    curl -fsSL https://get.docker.com | sh
  fi

  sudo usermod -aG docker "$USER" || true
  echo "[docker] updated: $(after)"
  exit 0
fi

echo "Please install Docker following https://docs.docker.com/engine/install/"


