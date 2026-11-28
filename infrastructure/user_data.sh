#!/bin/bash
# =============================================================================
# EC2 Bootstrap Script - Prepares Ubuntu 22.04 with Docker, Minikube, kubectl, Nginx
# =============================================================================
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

echo "=== [1/6] Updating OS packages ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -yq \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold"

echo "=== [2/6] Adding 2GB swap space ==="
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== [3/6] Installing Docker, Nginx, conntrack, Git, MySQL client ==="
apt-get install -y \
  git \
  curl \
  wget \
  gnupg \
  lsb-release \
  apt-transport-https \
  ca-certificates \
  conntrack \
  nginx \
  mysql-client \
  jq \
  unzip \
  docker.io

systemctl enable --now docker
systemctl enable --now nginx
usermod -aG docker ubuntu

echo "=== [4/6] Installing kubectl ==="
KUBECTL_VER=$(curl -fsSL https://dl.k8s.io/release/stable.txt)
curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl
chmod +x /usr/local/bin/kubectl

echo "=== [5/6] Installing Minikube ==="
curl -fsSL "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64" -o /usr/local/bin/minikube
chmod +x /usr/local/bin/minikube

echo "=== [6/6] Installing Trivy vulnerability scanner ==="
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" > /etc/apt/sources.list.d/trivy.list
apt-get update -y
apt-get install -y trivy

echo "=== Bootstrap complete ==="
touch /var/log/bootstrap-complete.log
