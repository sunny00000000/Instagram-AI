#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/bootstrap_oci.sh"
  exit 1
fi

APP_USER="${SUDO_USER:-ubuntu}"
apt-get update
apt-get install -y ca-certificates curl git gnupg ufw unattended-upgrades
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "${APP_USER}"

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

mkdir -p /opt/cryptopulse
chown "${APP_USER}:${APP_USER}" /opt/cryptopulse

cat >/etc/sysctl.d/99-cryptopulse.conf <<SYSCTL
vm.swappiness=10
fs.file-max=2097152
net.core.somaxconn=4096
SYSCTL
sysctl --system >/dev/null

echo "Bootstrap complete. Log out and log in again so Docker group membership takes effect."
