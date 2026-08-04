#!/bin/bash
# Bootstrap for the vehicle-core-service host (Amazon Linux 2023).
# Installs docker + compose plugin and prepares the app directory.
# The deploy itself (image pull, .env materialization from SSM, compose up,
# health check) is done by deploy/deploy.sh via SSM Run Command.
set -euxo pipefail

COMPOSE_VERSION="v2.32.4"
COMPOSE_RELEASE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}"

dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

# Download pinned compose binary and verify it against the official
# checksums.txt of the SAME pinned release (security item L6 — rejects a
# corrupted/tampered binary before it is ever installed).
mkdir -p /usr/local/lib/docker/cli-plugins
workdir="$(mktemp -d)"
curl -fsSL "${COMPOSE_RELEASE_URL}/docker-compose-linux-x86_64" \
  -o "${workdir}/docker-compose-linux-x86_64"
curl -fsSL "${COMPOSE_RELEASE_URL}/checksums.txt" -o "${workdir}/checksums.txt"
(cd "${workdir}" && grep ' docker-compose-linux-x86_64$' checksums.txt | sha256sum -c -)
mv "${workdir}/docker-compose-linux-x86_64" /usr/local/lib/docker/cli-plugins/docker-compose
rm -rf "${workdir}"
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version

mkdir -p /opt/vehicle-core-service
chown ec2-user:ec2-user /opt/vehicle-core-service
