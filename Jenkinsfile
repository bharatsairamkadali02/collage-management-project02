// ══════════════════════════════════════════════════════════════════════
//  EduManage Pro — Jenkins CI/CD Pipeline (EC2 + Docker + RDS MySQL + S3)
//  Repo   : https://github.com/bharatsairamkadali02/collage-management-project02.git
//  Image  : kadalibharatsairam01/college-management
//  Infra  : AWS VPC, Subnets, IGW, Route Tables, SGs, EC2, RDS MySQL, S3
// ══════════════════════════════════════════════════════════════════════
//
// JENKINS CREDENTIALS REQUIRED (Manage Jenkins → Credentials):
//   dockerhub-creds   → Username/Password  (Docker Hub login)
//   aws-credentials   → AWS Credentials    (IAM Access Key + Secret Key)
//   rds-password      → Secret text        (RDS MySQL password)
//   ec2-ssh-key       → SSH Username with private key (ubuntu + .pem key)
//
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'PROVISION_INFRA',
            defaultValue: false,
            description: 'Create/update AWS infrastructure (VPC, Subnets, IGW, Routes, SGs, EC2, RDS MySQL, S3) via Terraform'
        )
        booleanParam(
            name: 'DESTROY_INFRA',
            defaultValue: false,
            description: 'DANGER: Destroy the AWS infrastructure managed by Terraform in infrastructure/'
        )
        string(
            name: 'EC2_HOST',
            defaultValue: '',
            description: 'Optional EC2 public IP (auto-detected from Terraform output if empty)'
        )
        string(
            name: 'RDS_HOST',
            defaultValue: '',
            description: 'Optional RDS endpoint host (auto-detected from Terraform output if empty)'
        )
        string(
            name: 'S3_BUCKET',
            defaultValue: '',
            description: 'Optional S3 bucket name (auto-detected from Terraform output if empty)'
        )
    }

    environment {
        DOCKER_IMAGE     = "kadalibharatsairam01/college-management"
        DOCKER_TAG       = "${BUILD_NUMBER}"
        DOCKER_LATEST    = "${DOCKER_IMAGE}:latest"
        DOCKER_VERSIONED = "${DOCKER_IMAGE}:${DOCKER_TAG}"

        GIT_REPO         = "https://github.com/bharatsairamkadali02/collage-management-project02.git"
        GIT_BRANCH       = "main"

        AWS_REGION       = "ap-south-1"
        INFRA_DIR        = "infrastructure"

        DB_NAME          = "college_management"
        DB_USER          = "admin"
        DB_PORT          = "3306"
        CONTAINER_NAME   = "college-app"
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    stages {

        stage('0. Destroy Infrastructure (Optional)') {
            when {
                expression { return params.DESTROY_INFRA == true }
            }
            steps {
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
                        cd ${INFRA_DIR}
                        terraform init
                        terraform destroy -auto-approve
                    """
                }
            }
        }

        stage('1. Clone Repository') {
            steps {
                git branch: "${GIT_BRANCH}", url: "${GIT_REPO}"
                sh 'ls -la'
            }
        }

        stage('2. Provision AWS Infrastructure (Terraform)') {
            when {
                expression { return params.PROVISION_INFRA == true }
            }
            steps {
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
                        if ! command -v terraform &> /dev/null; then
                            wget -qO- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
                            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com \$(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
                            apt-get update -qq && apt-get install -y terraform
                        fi

                        cd ${INFRA_DIR}
                        terraform init
                        terraform apply -auto-approve

                        echo "EC2_PUBLIC_IP=\$(terraform output -raw ec2_public_ip)" > ../infra_outputs.env
                        echo "RDS_ADDRESS=\$(terraform output -raw rds_address)" >> ../infra_outputs.env
                        echo "S3_BUCKET_OUT=\$(terraform output -raw s3_bucket_name)" >> ../infra_outputs.env
                        cat ../infra_outputs.env
                    """
                }
            }
        }

        stage('3. Build Docker Image') {
            steps {
                sh """
                    docker build --no-cache \\
                        -t ${DOCKER_VERSIONED} \\
                        -t ${DOCKER_LATEST} \\
                        .
                    docker images | grep college-management
                """
            }
        }

        stage('4. Trivy Vulnerability Scan') {
            steps {
                sh """
                    if ! command -v trivy &> /dev/null; then
                        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg
                        echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb \$(lsb_release -sc) main" | tee /etc/apt/sources.list.d/trivy.list
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
                        echo "CRITICAL vulnerabilities detected: \$CRITICAL_COUNT"
                        exit 1
                    fi
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.txt', allowEmptyArchive: true
                }
            }
        }

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
                    """
                }
            }
        }

        stage('6. Deploy Docker Container to EC2 (RDS + S3)') {
            steps {
                withCredentials([
                    string(credentialsId: 'rds-password', variable: 'RDS_PASSWORD'),
                    sshUserPrivateKey(
                        credentialsId: 'ec2-ssh-key',
                        keyFileVariable: 'SSH_KEY_FILE',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh """
                        TARGET_EC2="${params.EC2_HOST}"
                        TARGET_RDS="${params.RDS_HOST}"
                        TARGET_S3="${params.S3_BUCKET}"

                        if [ -f "infra_outputs.env" ]; then
                            source infra_outputs.env
                            [ -z "\$TARGET_EC2" ] && TARGET_EC2="\$EC2_PUBLIC_IP"
                            [ -z "\$TARGET_RDS" ] && TARGET_RDS="\$RDS_ADDRESS"
                            [ -z "\$TARGET_S3" ] && TARGET_S3="\$S3_BUCKET_OUT"
                        fi

                        if [ -z "\$TARGET_EC2" ] || [ -z "\$TARGET_RDS" ] || [ -z "\$TARGET_S3" ]; then
                            echo "Missing EC2_HOST, RDS_HOST, or S3_BUCKET. Enable PROVISION_INFRA or set parameters."
                            exit 1
                        fi

                        SECRET_KEY_VAL=\$(openssl rand -hex 32)

                        ssh -o StrictHostKeyChecking=no -i "\$SSH_KEY_FILE" "\${SSH_USER}@\${TARGET_EC2}" bash -s <<EOF
set -e
docker pull ${DOCKER_LATEST}
docker rm -f ${CONTAINER_NAME} 2>/dev/null || true
docker run -d \\
  --name ${CONTAINER_NAME} \\
  -p 8080:5000 \\
  -e FLASK_ENV=production \\
  -e SESSION_COOKIE_SECURE=false \\
  -e SECRET_KEY="\${SECRET_KEY_VAL}" \\
  -e DATABASE_HOST="\${TARGET_RDS}" \\
  -e DATABASE_PORT="${DB_PORT}" \\
  -e DATABASE_NAME="${DB_NAME}" \\
  -e DATABASE_USER="${DB_USER}" \\
  -e DATABASE_PASSWORD="\$RDS_PASSWORD" \\
  -e AWS_REGION="${AWS_REGION}" \\
  -e S3_BUCKET_NAME="\${TARGET_S3}" \\
  -e INITIAL_ADMIN_EMAIL="admin@college.edu" \\
  -e INITIAL_ADMIN_PASSWORD="AdminPassword123!" \\
  --restart unless-stopped \\
  ${DOCKER_LATEST}
EOF

                        echo "Waiting for container health check..."
                        for i in 1 2 3 4 5 6; do
                            CODE=\$(curl -s -o /dev/null -w "%{http_code}" "http://\${TARGET_EC2}:8080/health" || echo "000")
                            if [ "\$CODE" = "200" ]; then
                                echo "Application healthy at http://\${TARGET_EC2}:8080"
                                break
                            fi
                            sleep 10
                        done
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
