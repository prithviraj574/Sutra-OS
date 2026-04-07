#!/usr/bin/env bash
set -euo pipefail

FC_VERSION="${FC_VERSION:-v1.7.0}"
ARCH="$(uname -m)"
INSTALL_DIR="/usr/local/bin"
SUTRA_DIR="/opt/sutra"
HOST_MANAGER_DIR="/opt/sutra/host_manager"
HOST_VENV="/opt/sutra/venv"

apt-get update -qq
apt-get install -y \
  curl \
  debootstrap \
  e2fsprogs \
  git \
  iproute2 \
  iptables \
  jq \
  python3 \
  python3-pip \
  python3-venv \
  wget

if [ ! -e /dev/kvm ]; then
  echo "/dev/kvm not found; nested virtualization is required"
  exit 1
fi

mkdir -p "$SUTRA_DIR" "$HOST_MANAGER_DIR" /var/agents

FC_RELEASE_URL="https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}"
wget -qO /tmp/firecracker.tgz "${FC_RELEASE_URL}/firecracker-${FC_VERSION}-${ARCH}.tgz"
tar -xf /tmp/firecracker.tgz -C /tmp
cp "/tmp/release-${FC_VERSION}-${ARCH}/firecracker-${FC_VERSION}-${ARCH}" "${INSTALL_DIR}/firecracker"
cp "/tmp/release-${FC_VERSION}-${ARCH}/jailer-${FC_VERSION}-${ARCH}" "${INSTALL_DIR}/jailer"
chmod +x "${INSTALL_DIR}/firecracker" "${INSTALL_DIR}/jailer"

python3 -m venv "$HOST_VENV"
"$HOST_VENV/bin/pip" install -q \
  fastapi \
  google-cloud-compute \
  httpx \
  pydantic \
  uvicorn

cat > /etc/systemd/system/sutra-host-manager.service << 'EOF'
[Unit]
Description=Sutra Host Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sutra
EnvironmentFile=/opt/sutra/.env
ExecStart=/opt/sutra/venv/bin/uvicorn host_manager.main:app --app-dir /opt/sutra --host 0.0.0.0 --port 8787 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sutra-host-manager

if ! grep -q '^net.ipv4.ip_forward = 1$' /etc/sysctl.conf; then
  echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
fi
sysctl -p
