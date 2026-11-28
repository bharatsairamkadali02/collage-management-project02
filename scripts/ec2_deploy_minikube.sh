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

for tool in docker kubectl minikube nginx; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: Required tool '$tool' is not installed on EC2."
        exit 1
    fi
done

if ! minikube status >/dev/null 2>&1; then
    echo "Starting Minikube Kubernetes cluster on EC2..."
    minikube start --driver=docker --cpus=2 --memory=2200mb --wait=all
else
    echo "Minikube is already running."
    minikube update-context
fi

if [ -f /tmp/app-image.tar.gz ]; then
    echo "Loading Trivy-scanned Docker image into Minikube (no Docker Hub required)..."
    gunzip -c /tmp/app-image.tar.gz > /tmp/app-image.tar
    rm -f /tmp/app-image.tar.gz
    minikube image load /tmp/app-image.tar
    rm -f /tmp/app-image.tar
    minikube image ls | grep college-management || true
else
    echo "ERROR: /tmp/app-image.tar.gz not found on EC2."
    exit 1
fi

RDS_PASS_DECODED=$(printf '%s' "$RDS_PASS_B64" | base64 -d)

echo "Applying Kubernetes manifests in namespace 'college-management'..."
kubectl apply -f /tmp/k8s/namespace.yaml

kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: college-app-config
  namespace: college-management
data:
  FLASK_ENV: "production"
  SESSION_COOKIE_SECURE: "false"
  DB_HOST: "${TARGET_RDS}"
  DB_PORT: "${DB_PORT}"
  DB_NAME: "${DB_NAME}"
  DB_USER: "${DB_USER}"
  AWS_REGION: "${AWS_REGION}"
  S3_BUCKET_NAME: "${TARGET_S3}"
  INITIAL_ADMIN_EMAIL: "admin@college.edu"
EOF

kubectl create secret generic college-app-secret \
  --namespace=college-management \
  --from-literal=DB_PASSWORD="$RDS_PASS_DECODED" \
  --from-literal=SECRET_KEY="$SECRET_KEY_VAL" \
  --from-literal=INITIAL_ADMIN_PASSWORD="AdminPassword123!" \
  --dry-run=client -o yaml | kubectl apply -f -

sed "s|image: kadalibharatsairam01/college-management:latest|image: ${DOCKER_VERSIONED}|g" /tmp/k8s/deployment.yaml | kubectl apply -f -
kubectl apply -f /tmp/k8s/service.yaml
rm -rf /tmp/k8s

echo "Waiting for Kubernetes Deployment rollout..."
kubectl rollout status deployment/college-app -n college-management --timeout=5m

echo "=== Pods in college-management ==="
kubectl get pods -n college-management -o wide
echo "=== Services in college-management ==="
kubectl get svc -n college-management

POD_NAME=$(kubectl get pods -n college-management -l app=college-app -o jsonpath='{.items[0].metadata.name}')
echo "Initializing RDS database and verifying S3 access inside pod: ${POD_NAME}"
for i in 1 2 3; do
    if kubectl exec -n college-management "$POD_NAME" -- python database.py; then
        break
    fi
    sleep 3
done
kubectl exec -n college-management "$POD_NAME" -- python -c "import boto3, os; boto3.client('s3', region_name=os.environ['AWS_REGION']).head_bucket(Bucket=os.environ['S3_BUCKET_NAME']); print('S3 connection verified from Minikube pod!')"

MINIKUBE_IP=$(minikube ip)
echo "Configuring Nginx reverse proxy on EC2 -> http://${MINIKUBE_IP}:30080 ..."
sudo tee /etc/nginx/sites-available/college-minikube >/dev/null <<NGINX_EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    listen 8080 default_server;
    listen [::]:8080 default_server;

    client_max_body_size 50M;

    location / {
        proxy_pass http://${MINIKUBE_IP}:30080;
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
NGINX_EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/college-minikube /etc/nginx/sites-enabled/college-minikube
sudo nginx -t
sudo systemctl restart nginx

curl -fsS http://127.0.0.1:8080/health
echo ""
echo "Minikube deployment and Nginx proxy verified locally on EC2!"
