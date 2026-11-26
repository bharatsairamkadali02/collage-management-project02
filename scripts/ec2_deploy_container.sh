#!/usr/bin/env bash
set -euo pipefail

DOCKER_VERSIONED="$1"
DOCKER_LATEST="$2"
CONTAINER_NAME="$3"
TARGET_RDS="$4"
DB_PORT="$5"
DB_NAME="$6"
DB_USER="$7"
AWS_REGION="$8"
TARGET_S3="$9"
SECRET_KEY_VAL="${10}"
RDS_PASS_B64="${11}"

echo "Waiting for Docker bootstrap on EC2..."
for i in $(seq 1 36); do
    if command -v docker >/dev/null 2>&1 && sudo systemctl is-active --quiet docker && [ -f /var/log/bootstrap-complete.log ]; then
        break
    fi
    sleep 5
done

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed or failed to start on EC2."
    exit 1
fi

RDS_PASS_DECODED=$(printf '%s' "$RDS_PASS_B64" | base64 -d)

if [ -f /tmp/app-image.tar.gz ]; then
    echo "Loading Docker image transferred from Jenkins (no Docker Hub required)..."
    sudo docker load -i /tmp/app-image.tar.gz
    rm -f /tmp/app-image.tar.gz
else
    echo "Error: /tmp/app-image.tar.gz not found on EC2."
    exit 1
fi

sudo docker tag "$DOCKER_VERSIONED" "$DOCKER_LATEST"
sudo docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

sudo docker run -d \
  --name "$CONTAINER_NAME" \
  -p 8080:5000 \
  -e FLASK_ENV=production \
  -e SESSION_COOKIE_SECURE=false \
  -e SECRET_KEY="$SECRET_KEY_VAL" \
  -e DATABASE_HOST="$TARGET_RDS" \
  -e DATABASE_PORT="$DB_PORT" \
  -e DATABASE_NAME="$DB_NAME" \
  -e DATABASE_USER="$DB_USER" \
  -e DATABASE_PASSWORD="$RDS_PASS_DECODED" \
  -e AWS_REGION="$AWS_REGION" \
  -e S3_BUCKET_NAME="$TARGET_S3" \
  -e INITIAL_ADMIN_EMAIL="admin@college.edu" \
  -e INITIAL_ADMIN_PASSWORD="AdminPassword123!" \
  --restart unless-stopped \
  "$DOCKER_VERSIONED"

sleep 5
for i in 1 2 3; do
    if sudo docker exec "$CONTAINER_NAME" python database.py; then
        break
    fi
    sleep 3
done
sudo docker exec "$CONTAINER_NAME" python -c "import boto3, os; boto3.client('s3', region_name=os.environ['AWS_REGION']).head_bucket(Bucket=os.environ['S3_BUCKET_NAME']); print('S3 connection verified!')"
