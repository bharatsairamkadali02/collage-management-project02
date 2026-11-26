#!/bin/bash
# =============================================================================
# EC2 Bootstrap Script - Prepares Ubuntu 22.04 with Docker, Git, Trivy, MySQL
# =============================================================================
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

echo "=== [1/5] Updating OS packages ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -yq \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold"

echo "=== [2/5] Adding 2GB swap space for Docker builds ==="
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== [3/5] Installing Git, Docker, MySQL client, and utilities ==="
apt-get install -y \
  git \
  curl \
  wget \
  gnupg \
  lsb-release \
  apt-transport-https \
  ca-certificates \
  mysql-client \
  jq \
  unzip \
  docker.io

systemctl enable --now docker
usermod -aG docker ubuntu

echo "=== [4/5] Installing Trivy vulnerability scanner ==="
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" > /etc/apt/sources.list.d/trivy.list
apt-get update -y
apt-get install -y trivy

echo "=== [5/5] Bootstrap complete ==="
touch /var/log/bootstrap-complete.log
