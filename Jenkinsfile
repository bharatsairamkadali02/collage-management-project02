// ══════════════════════════════════════════════════════════════════════
//  EduManage Pro — Full CI/CD Pipeline with Infrastructure as Code
//  Repo   : https://github.com/bharatsairamkadali02/collage-management-project02.git
//  Image  : kadalibharatsairam01/college-management
//  Infra  : Complete AWS (VPC, EKS Cluster, Worker Nodes, RDS MySQL, S3)
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'PROVISION_INFRA',
            defaultValue: false,
            description: 'Check this to create/update the ENTIRE new AWS infrastructure (VPC, EKS, RDS, S3) using Terraform'
        )
        booleanParam(
            name: 'DESTROY_INFRA',
            defaultValue: false,
            description: 'DANGER: Check this to destroy the infrastructure created by Terraform'
        )
    }

    environment {
        // Docker Hub
        DOCKER_IMAGE      = "kadalibharatsairam01/college-management"
        DOCKER_TAG        = "${BUILD_NUMBER}"
        DOCKER_LATEST     = "${DOCKER_IMAGE}:latest"
        DOCKER_VERSIONED  = "${DOCKER_IMAGE}:${DOCKER_TAG}"

        // GitHub
        GIT_REPO          = "https://github.com/bharatsairamkadali02/collage-management-project02.git"
        GIT_BRANCH        = "main"

        // AWS / EKS Defaults
        AWS_REGION        = "ap-south-1"
        EKS_CLUSTER_NAME  = "my-eks-cluster"

        // Application
        APP_NAME          = "college-app"
        K8S_DIR           = "k8s"
        INFRA_DIR         = "infrastructure"

        // Database Default fallback
        DB_HOST           = "college-management-rds.c5k2wsog2wjy.ap-south-1.rds.amazonaws.com"
        DB_NAME           = "college_management"
        DB_USER           = "admin"
        DB_PORT           = "3306"
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 90, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    stages {

        // ──────────────────────────────────────────────────────────────
        // STAGE 0: Destroy Infrastructure (If Requested)
        // ──────────────────────────────────────────────────────────────
        stage('0. Destroy Infrastructure (Optional)') {
            when {
                expression { return params.DESTROY_INFRA == true }
            }
            steps {
                echo "⚠️  DESTROYING ENTIRE AWS INFRASTRUCTURE..."
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-credentials',
                    accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                    secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                ]]) {
                    sh """
                        cd ${INFRA_DIR}
                        terraform init
                        terraform destroy -auto-approve
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 1: Clone Repository
        // ──────────────────────────────────────────────────────────────
        stage('1. Clone Repository') {
            steps {
                echo "Cloning source code from ${GIT_REPO}..."
                git branch: "${GIT_BRANCH}", url: "${GIT_REPO}"
                sh 'ls -la'
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 2: Provision Entire New AWS Infrastructure (Terraform)
        // ──────────────────────────────────────────────────────────────
        stage('2. Provision Entire AWS Infrastructure') {
            when {
                expression { return params.PROVISION_INFRA == true }
            }
            steps {
                echo "============================================"
                echo "  Provisioning New AWS Infrastructure:"
                echo "  • Unified VPC + Subnets (Multi-AZ)"
                echo "  • EKS Cluster + Managed Node Group"
                echo "  • RDS MySQL Database (in same VPC)"
                echo "  • S3 Storage Bucket"
                echo "============================================"
                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-credentials',
                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ],
                    string(credentialsId: 'rds-password', variable: 'TF_VAR_db_password')
                ]) {
                    sh """
                        # Install Terraform if not present
                        if ! command -v terraform &> /dev/null; then
                            echo "Installing Terraform..."
                            wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
                            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com \$(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
                            apt-get update -qq && apt-get install -y terraform
                        fi

                        cd ${INFRA_DIR}
                        terraform init
                        terraform apply -auto-approve

                        # Export live RDS endpoint and EKS cluster name
                        NEW_RDS_HOST=\$(terraform output -raw rds_address 2>/dev/null || echo "")
                        NEW_CLUSTER_NAME=\$(terraform output -raw eks_cluster_name 2>/dev/null || echo "")

                        if [ -n "\$NEW_RDS_HOST" ]; then
                            echo "RDS_HOST=\$NEW_RDS_HOST" > ../infra_outputs.env
                        fi
                        if [ -n "\$NEW_CLUSTER_NAME" ]; then
                            echo "EKS_CLUSTER_NAME=\$NEW_CLUSTER_NAME" >> ../infra_outputs.env
                        fi

                        echo "✅ Entire Infrastructure Created Successfully!"
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 3: Build Docker Image
        // ──────────────────────────────────────────────────────────────
        stage('3. Build Docker Image') {
            steps {
                echo "Building Docker image: ${DOCKER_VERSIONED}..."
                sh """
                    docker build --no-cache \\
                        -t ${DOCKER_VERSIONED} \\
                        -t ${DOCKER_LATEST} \\
                        .
                """
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 4: Trivy Security Scan
        // ──────────────────────────────────────────────────────────────
        stage('4. Trivy Security Vulnerability Scan') {
            steps {
                echo "Scanning image for vulnerabilities..."
                sh """
                    if ! command -v trivy &> /dev/null; then
                        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add -
                        echo "deb https://aquasecurity.github.io/trivy-repo/deb \$(lsb_release -sc) main" | tee /etc/apt/sources.list.d/trivy.list
                        apt-get update -qq && apt-get install -y trivy
                    fi

                    trivy image \\
                        --ignore-unfixed \\
                        --severity HIGH,CRITICAL \\
                        --format table \\
                        --output trivy-report.txt \\
                        ${DOCKER_LATEST}

                    cat trivy-report.txt

                    CRITICAL_COUNT=\$(trivy image --ignore-unfixed --severity CRITICAL \\
                        --format json ${DOCKER_LATEST} 2>/dev/null | \\
                        python3 -c "import json,sys; d=json.load(sys.stdin); \\
                        print(sum(len([v for v in (r.get('Vulnerabilities') or []) \\
                        if v.get('Severity')=='CRITICAL']) \\
                        for r in (d.get('Results') or [])))" 2>/dev/null || echo 0)

                    if [ "\$CRITICAL_COUNT" -gt "0" ]; then
                        echo "❌ Critical vulnerabilities detected!"
                        exit 1
                    fi

                    echo "✅ Scan passed with 0 critical vulnerabilities!"
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.txt', allowEmptyArchive: true
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 5: Push to Docker Hub
        // ──────────────────────────────────────────────────────────────
        stage('5. Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        echo "\$DOCKER_PASS" | docker login -u "\$DOCKER_USER" --password-stdin
                        docker push ${DOCKER_VERSIONED}
                        docker push ${DOCKER_LATEST}
                        docker logout
                        echo "✅ Image pushed to Docker Hub!"
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 6: Deploy Application to 2-Tier Architecture
        // ──────────────────────────────────────────────────────────────
        stage('6. Deploy to EKS (2-Tier: App + RDS)') {
            steps {
                echo "Deploying application to EKS..."
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

                        # Check if dynamic outputs exist from Terraform
                        TARGET_RDS="${DB_HOST}"
                        TARGET_CLUSTER="${EKS_CLUSTER_NAME}"
                        if [ -f "infra_outputs.env" ]; then
                            source infra_outputs.env
                            [ -n "\$RDS_HOST" ] && TARGET_RDS="\$RDS_HOST"
                            [ -n "\$EKS_CLUSTER_NAME" ] && TARGET_CLUSTER="\$EKS_CLUSTER_NAME"
                        fi

                        echo "Target EKS Cluster: \$TARGET_CLUSTER"
                        echo "Target RDS Host   : \$TARGET_RDS"

                        # Ensure kubectl is configured
                        aws eks update-kubeconfig --region ${AWS_REGION} --name \$TARGET_CLUSTER

                        # Tier 2: ConfigMap (Database Connection)
                        kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: college-app-config
data:
  FLASK_ENV: "development"
  DB_HOST: "\$TARGET_RDS"
  DB_PORT: "${DB_PORT}"
  DB_NAME: "${DB_NAME}"
  DB_USER: "${DB_USER}"
  INITIAL_ADMIN_EMAIL: "admin@college.edu"
EOF

                        # Tier 2: Secret (Database Credentials)
                        kubectl create secret generic college-app-secret \\
                            --from-literal=DB_PASSWORD="\$RDS_PASSWORD" \\
                            --from-literal=SECRET_KEY="\$(openssl rand -hex 32)" \\
                            --from-literal=INITIAL_ADMIN_PASSWORD="AdminPassword123!" \\
                            --dry-run=client -o yaml | kubectl apply -f -

                        # Tier 1: Frontend/App Deployment
                        kubectl apply -f ${K8S_DIR}/deployment.yaml
                        kubectl set image deployment/${APP_NAME} ${APP_NAME}=${DOCKER_VERSIONED}

                        # Tier 1: Service (Load Balancer)
                        kubectl apply -f ${K8S_DIR}/service.yaml

                        echo "✅ Deployment updated successfully!"
                    """
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // STAGE 7: Verify Health & Connectivity
        // ──────────────────────────────────────────────────────────────
        stage('7. Verify 2-Tier Health') {
            steps {
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

                        TARGET_CLUSTER="${EKS_CLUSTER_NAME}"
                        if [ -f "infra_outputs.env" ]; then
                            source infra_outputs.env
                            [ -n "\$EKS_CLUSTER_NAME" ] && TARGET_CLUSTER="\$EKS_CLUSTER_NAME"
                        fi

                        aws eks update-kubeconfig --region ${AWS_REGION} --name \$TARGET_CLUSTER

                        echo "Waiting for rollout..."
                        kubectl rollout status deployment/${APP_NAME} --timeout=5m

                        echo "── Pod Status ──"
                        kubectl get pods -o wide

                        LB_URL=\$(kubectl get svc college-app-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
                        if [ -n "\$LB_URL" ]; then
                            echo "✅ Application Live at: http://\${LB_URL}"
                            echo "✅ Health Endpoint    : http://\${LB_URL}/health"
                        fi
                    """
                }
            }
        }
    }

    post {
        always {
            sh """
                docker rmi ${DOCKER_VERSIONED} || true
                docker rmi ${DOCKER_LATEST} || true
                rm -f infra_outputs.env || true
            """
        }
    }
}
