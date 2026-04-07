#!/usr/bin/env bash
set -euo pipefail

ROOTFS_SIZE_MB="${ROOTFS_SIZE_MB:-2048}"
OUTPUT="${OUTPUT:-/opt/sutra/base-rootfs.ext4}"
MOUNT_DIR="${MOUNT_DIR:-/tmp/sutra-rootfs}"
UBUNTU_RELEASE="${UBUNTU_RELEASE:-jammy}"
HERMES_BIN_SOURCE="${HERMES_BIN_SOURCE:-}"
HERMES_AGENT_SOURCE="${HERMES_AGENT_SOURCE:-}"
HERMES_PORT="${HERMES_PORT:-8642}"

cleanup() {
  if mountpoint -q "$MOUNT_DIR"; then
    umount "$MOUNT_DIR"
  fi
}

trap cleanup EXIT

dd if=/dev/null of="$OUTPUT" bs=1M seek="$ROOTFS_SIZE_MB"
mkfs.ext4 -F "$OUTPUT"
mkdir -p "$MOUNT_DIR"
mount -o loop "$OUTPUT" "$MOUNT_DIR"

debootstrap --arch=amd64 "$UBUNTU_RELEASE" "$MOUNT_DIR" http://archive.ubuntu.com/ubuntu/

chroot "$MOUNT_DIR" useradd -m -s /bin/bash user || true
chroot "$MOUNT_DIR" mkdir -p /usr/local/bin /etc/systemd/system/multi-user.target.wants /home/user/.local/lib/hermes-agent

cat > "$MOUNT_DIR/usr/local/bin/sutra-guest-init.sh" << 'EOF'
#!/bin/bash
set -euo pipefail

mkdir -p /mnt/agent-data
if [ -b /dev/vdb ]; then
  mountpoint -q /mnt/agent-data || mount /dev/vdb /mnt/agent-data
fi

mkdir -p /mnt/agent-data/.hermes
mkdir -p /mnt/agent-data/workspace
mkdir -p /home/user

ln -sfn /mnt/agent-data/.hermes /home/user/.hermes
ln -sfn /mnt/agent-data/workspace /home/user/workspace
chown -R user:user /mnt/agent-data /home/user
EOF

cat > "$MOUNT_DIR/etc/systemd/system/sutra-agent-storage.service" << 'EOF'
[Unit]
Description=Sutra Agent Storage Setup
After=local-fs.target
Before=sutra-hermes.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/sutra-guest-init.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

cat > "$MOUNT_DIR/etc/systemd/system/sutra-hermes.service" << EOF
[Unit]
Description=Sutra Hermes Agent
After=network-online.target sutra-agent-storage.service
Requires=sutra-agent-storage.service

[Service]
Type=simple
User=user
Environment=HOME=/home/user
WorkingDirectory=/home/user
ExecStart=/home/user/hermes serve --port ${HERMES_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chmod +x "$MOUNT_DIR/usr/local/bin/sutra-guest-init.sh"

ln -sfn /etc/systemd/system/sutra-agent-storage.service \
  "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/sutra-agent-storage.service"
ln -sfn /etc/systemd/system/sutra-hermes.service \
  "$MOUNT_DIR/etc/systemd/system/multi-user.target.wants/sutra-hermes.service"

if [[ -n "$HERMES_BIN_SOURCE" ]]; then
  install -m 0755 "$HERMES_BIN_SOURCE" "$MOUNT_DIR/home/user/hermes"
fi

if [[ -n "$HERMES_AGENT_SOURCE" ]]; then
  mkdir -p "$MOUNT_DIR/home/user/.local/lib/hermes-agent"
  cp -R "$HERMES_AGENT_SOURCE"/. "$MOUNT_DIR/home/user/.local/lib/hermes-agent/"
fi

chroot "$MOUNT_DIR" chown -R user:user /home/user
