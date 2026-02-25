#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"

before() { command -v docker >/dev/null 2>&1 && docker --version || true; }
after() { command -v docker >/dev/null 2>&1 && docker --version || true; }

install_docker() {
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
    return 0
  fi

  echo "Please install Docker following https://docs.docker.com/engine/install/"
}

uninstall_docker() {
  echo "[docker] Docker uninstall is a system-level operation." >&2
  echo "[docker] To remove Docker Engine, run:" >&2
  echo "[docker]   sudo apt-get remove docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin" >&2
  echo "[docker]   sudo apt-get purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin" >&2
  echo "[docker]   sudo rm -rf /var/lib/docker /var/lib/containerd" >&2
  echo "[docker] See: https://docs.docker.com/engine/install/ubuntu/#uninstall-docker-engine" >&2
}

case "$ACTION" in
  install|update) install_docker ;;
  uninstall) uninstall_docker ;;
  *) echo "Usage: $0 {install|update|uninstall}" ; exit 2 ;;
esac
