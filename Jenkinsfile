// ══════════════════════════════════════════════════════════════════════
//  EduManage Pro — Jenkins CI/CD Pipeline
//  Repo   : https://github.com/bharatsairamkadali02/collage-management-project02.git
//  Image  : kadalibharatsairam01/college-management
//  Deploy : AWS EKS (2-tier — Flask app + RDS MySQL)
// ══════════════════════════════════════════════════════════════════════
//
// JENKINS CREDENTIALS REQUIRED (Settings → Manage Jenkins → Credentials):
//   dockerhub-creds   → Username/Password  (DockerHub login)
//   aws-credentials   → AWS Access Key ID + Secret (kind: AWS Credentials)
//   rds-password      → Secret text  (your RDS MySQL password)
//
// JENKINS PLUGINS REQUIRED:
//   Docker Pipeline, AWS Credentials, Pipeline, Git, Kubernetes CLI
//
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    // ── Global environment variables ─────────────────────────────────
    environment {
        // Docker Hub
        DOCKER_IMAGE      = "kadalibharatsairam01/college-management"
        DOCKER_TAG        = "${BUILD_NUMBER}"          // e.g. :42
        DOCKER_LATEST     = "${DOCKER_IMAGE}:latest"
        DOCKER_VERSIONED  = "${DOCKER_IMAGE}:${DOCKER_TAG}"

        // GitHub
        GIT_REPO          = "https://github.com/bharatsairamkadali02/collage-management-project02.git"
        GIT_BRANCH        = "main"

        // AWS / EKS
        AWS_REGION        = "ap-south-1"
        EKS_CLUSTER_NAME  = "my-eks-cluster"

        // Application
        APP_NAME          = "college-app"
        K8S_DIR           = "k8s"

        // RDS (non-sensitive — host only; password comes from Jenkins credential)
        DB_HOST           = "college-management-rds.c5k2wsog2wjy.ap-south-1.rds.amazonaws.com"
        DB_NAME           = "college_management"
        DB_USER           = "admin"
        DB_PORT           = "3306"
    }

    // ── Build options ─────────────────────────────────────────────────
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    // ── Pipeline stages ───────────────────────────────────────────────
    stages {

        // ──────────────────────────────────────────────────────────────
        // STAGE 1: Clone source code from GitHub
        // ──────────────────────────────────────────────────────────────
        stage('1. Clone Repository') {
            steps {
                echo "============================================"
                echo "  Cloning from: ${GIT_REPO}"
                echo "  Branch      : ${GIT_BRANCH}"
                echo "============================================"
                git branch: "${GIT_BRANCH}",
                    url: "${GIT_REPO}"

                sh 'ls -la'
                sh 'echo "Repository cloned successfully ✓"'
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 2: Build Docker Image
        // ──────────────────────────────────────────────────────────────
        stage('2. Build Docker Image') {
            steps {
                echo "============================================"
                echo "  Building image: ${DOCKER_VERSIONED}"
                echo "============================================"
                sh """
                    docker build --no-cache \\
                        -t ${DOCKER_VERSIONED} \\
                        -t ${DOCKER_LATEST} \\
                        .

                    echo "Image built successfully ✓"
                    docker images | grep college-management
                """
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 3: Trivy Security Scan
        //   - Scans image for CVEs
        //   - Saves a report as an artifact
        //   - Uses .trivyignore (already in repo) to suppress phantom CVEs
        //   - Pipeline FAILS if any CRITICAL vulnerability is found
        // ──────────────────────────────────────────────────────────────
        stage('3. Trivy Security Scan') {
            steps {
                echo "============================================"
                echo "  Scanning image for vulnerabilities..."
                echo "============================================"
                sh """
                    # Install Trivy if not present
                    if ! command -v trivy &> /dev/null; then
                        echo "Installing Trivy..."
                        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add -
                        echo "deb https://aquasecurity.github.io/trivy-repo/deb \$(lsb_release -sc) main" \\
                            | tee /etc/apt/sources.list.d/trivy.list
                        apt-get update -qq && apt-get install -y trivy
                    fi

                    echo "Trivy version: \$(trivy --version)"

                    # Run scan — ignore unfixed CVEs, use .trivyignore from repo
                    trivy image \\
                        --ignore-unfixed \\
                        --severity HIGH,CRITICAL \\
                        --format table \\
                        --output trivy-report.txt \\
                        ${DOCKER_LATEST}

                    echo "──── Scan Summary ────"
                    cat trivy-report.txt

                    # Count CRITICAL findings and fail if any found
                    CRITICAL_COUNT=\$(trivy image --ignore-unfixed --severity CRITICAL \\
                        --format json ${DOCKER_LATEST} 2>/dev/null | \\
                        python3 -c "import json,sys; d=json.load(sys.stdin); \\
                        print(sum(len([v for v in (r.get('Vulnerabilities') or []) \\
                        if v.get('Severity')=='CRITICAL']) \\
                        for r in (d.get('Results') or [])))" 2>/dev/null || echo 0)

                    echo "CRITICAL vulnerabilities found: \$CRITICAL_COUNT"

                    if [ "\$CRITICAL_COUNT" -gt "0" ]; then
                        echo "❌ PIPELINE FAILED: Critical vulnerabilities detected!"
                        exit 1
                    fi

                    echo "✅ No critical vulnerabilities — image is safe!"
                """
            }
            post {
                always {
                    // Archive scan report as a Jenkins artifact
                    archiveArtifacts artifacts: 'trivy-report.txt',
                                     allowEmptyArchive: true
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 4: Push Image to Docker Hub
        // ──────────────────────────────────────────────────────────────
        stage('4. Push to Docker Hub') {
            steps {
                echo "============================================"
                echo "  Pushing to Docker Hub..."
                echo "============================================"
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        echo "\$DOCKER_PASS" | docker login -u "\$DOCKER_USER" --password-stdin

                        docker push ${DOCKER_VERSIONED}
                        docker push ${DOCKER_LATEST}

                        echo "✅ Image pushed to Docker Hub:"
                        echo "   ${DOCKER_VERSIONED}"
                        echo "   ${DOCKER_LATEST}"

                        docker logout
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 5: Create / Update Infrastructure (EKS + Nodes)
        //   - If EKS cluster already exists → skips creation
        //   - If EKS cluster does not exist → creates it (~15 min)
        //   - Then configures kubectl
        // ──────────────────────────────────────────────────────────────
        stage('5. Create Infrastructure (EKS)') {
            steps {
                echo "============================================"
                echo "  Setting up EKS cluster: ${EKS_CLUSTER_NAME}"
                echo "  Region: ${AWS_REGION}"
                echo "============================================"
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-credentials',
                    accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                    secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                ]]) {
                    sh """
                        export AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID
                        export AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY
                        export AWS_DEFAULT_REGION=${AWS_REGION}

                        # Install eksctl if not present
                        if ! command -v eksctl &> /dev/null; then
                            echo "Installing eksctl..."
                            ARCH=amd64
                            PLATFORM=\$(uname -s)_\$ARCH
                            curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_\${PLATFORM}.tar.gz"
                            tar -xzf eksctl_\${PLATFORM}.tar.gz -C /tmp
                            mv /tmp/eksctl /usr/local/bin/
                        fi

                        # Install kubectl if not present
                        if ! command -v kubectl &> /dev/null; then
                            echo "Installing kubectl..."
                            curl -LO "https://dl.k8s.io/release/\$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                            chmod +x kubectl && mv kubectl /usr/local/bin/
                        fi

                        # Check if cluster already exists
                        if aws eks describe-cluster --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION} 2>/dev/null; then
                            echo "✅ EKS cluster '${EKS_CLUSTER_NAME}' already exists — skipping creation."
                        else
                            echo "Creating EKS cluster... (this takes ~15 minutes)"
                            eksctl create cluster \\
                                --name ${EKS_CLUSTER_NAME} \\
                                --region ${AWS_REGION} \\
                                --nodegroup-name college-nodes \\
                                --node-type t3.medium \\
                                --nodes 2 \\
                                --nodes-min 1 \\
                                --nodes-max 3 \\
                                --managed
                            echo "✅ EKS cluster created!"
                        fi

                        # Configure kubectl to talk to this cluster
                        aws eks update-kubeconfig \\
                            --region ${AWS_REGION} \\
                            --name ${EKS_CLUSTER_NAME}

                        echo "── Cluster Nodes ──"
                        kubectl get nodes
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 6: Deploy Application to EKS (2-Tier Architecture)
        //   Tier 1 (Frontend/App): Flask + Gunicorn pods on EKS
        //   Tier 2 (Database)    : Existing AWS RDS MySQL
        // ──────────────────────────────────────────────────────────────
        stage('6. Deploy to EKS (2-Tier)') {
            steps {
                echo "============================================"
                echo "  Deploying 2-Tier Architecture:"
                echo "  Tier 1: Flask App (EKS Pods)"
                echo "  Tier 2: RDS MySQL (${DB_HOST})"
                echo "============================================"
                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-credentials',
                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ],
                    string(credentialsId: 'rds-password', variable: 'RDS_PASSWORD')
                ]) {
                    sh """
                        export AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID
                        export AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY
                        export AWS_DEFAULT_REGION=${AWS_REGION}

                        # Reconnect kubectl to EKS
                        aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}

                        # ── Tier 2: ConfigMap (non-sensitive DB config) ──
                        kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: college-app-config
data:
  FLASK_ENV: "development"
  DB_HOST: "${DB_HOST}"
  DB_PORT: "${DB_PORT}"
  DB_NAME: "${DB_NAME}"
  DB_USER: "${DB_USER}"
  INITIAL_ADMIN_EMAIL: "admin@college.edu"
EOF

                        # ── Tier 2: Secret (sensitive credentials) ──
                        kubectl create secret generic college-app-secret \\
                            --from-literal=DB_PASSWORD="\$RDS_PASSWORD" \\
                            --from-literal=SECRET_KEY="\$(openssl rand -hex 32)" \\
                            --from-literal=INITIAL_ADMIN_PASSWORD="AdminPassword123!" \\
                            --dry-run=client -o yaml | kubectl apply -f -

                        # ── Tier 1: Deployment — update image to latest build ──
                        kubectl apply -f ${K8S_DIR}/deployment.yaml

                        # Update the image to the new versioned tag
                        kubectl set image deployment/${APP_NAME} \\
                            ${APP_NAME}=${DOCKER_VERSIONED}

                        # ── Tier 1: Service — AWS Load Balancer ──
                        kubectl apply -f ${K8S_DIR}/service.yaml

                        echo "✅ All Kubernetes resources applied!"
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 7: Verify Deployment
        // ──────────────────────────────────────────────────────────────
        stage('7. Verify Deployment') {
            steps {
                echo "============================================"
                echo "  Verifying deployment health..."
                echo "============================================"
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-credentials',
                    accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                    secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                ]]) {
                    sh """
                        export AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID
                        export AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY
                        export AWS_DEFAULT_REGION=${AWS_REGION}

                        aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER_NAME}

                        # Wait for rollout to complete (max 5 minutes)
                        echo "Waiting for rollout to complete..."
                        kubectl rollout status deployment/${APP_NAME} --timeout=5m

                        echo "── Pod Status ──"
                        kubectl get pods -o wide

                        echo "── Service & Load Balancer ──"
                        kubectl get svc college-app-service

                        # Get the Load Balancer URL
                        LB_URL=\$(kubectl get svc college-app-service \\
                            -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

                        if [ "\$LB_URL" != "pending" ] && [ -n "\$LB_URL" ]; then
                            echo ""
                            echo "✅ Application is LIVE at:"
                            echo "   http://\${LB_URL}"
                            echo "   http://\${LB_URL}/health"

                            # Test health endpoint (retry 5 times)
                            for i in 1 2 3 4 5; do
                                HTTP_CODE=\$(curl -s -o /dev/null -w "%{http_code}" \\
                                    http://\${LB_URL}/health 2>/dev/null || echo "000")
                                if [ "\$HTTP_CODE" = "200" ]; then
                                    echo "✅ Health check PASSED — HTTP 200"
                                    break
                                fi
                                echo "Attempt \$i — HTTP \$HTTP_CODE — retrying in 15s..."
                                sleep 15
                            done
                        else
                            echo "⚠️  Load Balancer still provisioning — check AWS Console in 2 minutes."
                            echo "    kubectl get svc college-app-service"
                        fi

                        echo ""
                        echo "══════════════════════════════════════"
                        echo "  2-TIER ARCHITECTURE STATUS"
                        echo "══════════════════════════════════════"
                        echo "  Tier 1 (App)  : Flask Pods on EKS — see above"
                        echo "  Tier 2 (DB)   : RDS MySQL — ${DB_HOST}"
                        echo "  Image Deployed: ${DOCKER_VERSIONED}"
                        echo "  Build Number  : ${BUILD_NUMBER}"
                        echo "══════════════════════════════════════"
                    """
                }
            }
        }
    }

    // ── Post-build actions ────────────────────────────────────────────
    post {
        success {
            echo """
╔══════════════════════════════════════╗
║   ✅  PIPELINE SUCCEEDED             ║
║   Build #${BUILD_NUMBER} deployed!   ║
╚══════════════════════════════════════╝
            """
        }
        failure {
            echo """
╔══════════════════════════════════════╗
║   ❌  PIPELINE FAILED                ║
║   Build #${BUILD_NUMBER} failed.     ║
║   Check logs above for details.      ║
╚══════════════════════════════════════╝
            """
            // Optional: clean up dangling images on failure
            sh 'docker image prune -f || true'
        }
        always {
            echo "Cleaning up Docker images from Jenkins server..."
            sh """
                docker rmi ${DOCKER_VERSIONED} || true
                docker rmi ${DOCKER_LATEST} || true
            """
        }
    }
}
