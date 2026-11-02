#!/usr/bin/env bash
# Deploy the checked-out application on its Ubuntu EC2 host.
# Usage: sudo bash scripts/deploy.sh
set -Eeuo pipefail

APP_DIR="/opt/college-app"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${APP_DIR}/.env"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo: sudo bash scripts/deploy.sh" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Create it from .env.example and set real values first." >&2
  exit 1
fi

required_vars=(SECRET_KEY DATABASE_HOST DATABASE_NAME DATABASE_USER DATABASE_PASSWORD S3_BUCKET_NAME INITIAL_ADMIN_EMAIL INITIAL_ADMIN_PASSWORD)
for var in "${required_vars[@]}"; do
  if ! grep -Eq "^${var}=.+" "${ENV_FILE}"; then
    echo "${var} is missing or empty in ${ENV_FILE}." >&2
    exit 1
  fi
done

if grep -Eq 'REPLACE_WITH|your-rds-endpoint|your-college-management-bucket|your-database-password|your-secret-key-change-this' "${ENV_FILE}"; then
  echo "Replace all example placeholders in ${ENV_FILE} before deploying." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip python3-dev nginx rsync build-essential pkg-config default-libmysqlclient-dev

if ! id -u appuser >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin appuser
fi

install -d -o appuser -g appuser -m 0755 "${APP_DIR}" /var/log/college-app
rsync -a --delete \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "${PROJECT_ROOT}/" "${APP_DIR}/"

if [[ ! -x "${APP_DIR}/venv/bin/python" ]]; then
  runuser -u appuser -- python3 -m venv "${APP_DIR}/venv"
fi
runuser -u appuser -- "${APP_DIR}/venv/bin/python" -m pip install --upgrade pip wheel
runuser -u appuser -- "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

chown -R appuser:appuser "${APP_DIR}"
chmod 600 "${ENV_FILE}"
chown appuser:appuser "${ENV_FILE}"
chown appuser:appuser /var/log/college-app

# Create missing tables and seed roles/admin. Existing accounts are not reset.
runuser -u appuser -- bash -c "cd '${APP_DIR}/backend' && '${APP_DIR}/venv/bin/python' database.py"

install -o root -g root -m 0644 "${APP_DIR}/config/college-management.service" /etc/systemd/system/college-management.service
install -o root -g root -m 0644 "${APP_DIR}/config/nginx.conf" /etc/nginx/sites-available/college-management
ln -sfn /etc/nginx/sites-available/college-management /etc/nginx/sites-enabled/college-management
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl daemon-reload
systemctl enable --now college-management
systemctl enable --now nginx
systemctl restart college-management
systemctl reload nginx

echo "Deployment finished. Service status:"
systemctl --no-pager --full status college-management
echo "Local health response:"
curl --fail --silent --show-error http://127.0.0.1/health
