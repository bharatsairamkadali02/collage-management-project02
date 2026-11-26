// ══════════════════════════════════════════════════════════════════════
//  EduManage Pro — Jenkins CI/CD Pipeline (EC2 + Docker + RDS MySQL + S3)
//  Repo   : https://github.com/bharatsairamkadali02/collage-management-project02.git
//  Image  : kadalibharatsairam01/college-management
//  Infra  : AWS VPC, Subnets, IGW, Route Tables, SGs, EC2, RDS MySQL, S3
//           (No Kubernetes / No EKS)
// ══════════════════════════════════════════════════════════════════════
//
// JENKINS CREDENTIALS REQUIRED (Manage Jenkins → Credentials):
//   dockerhub-creds   → Username/Password  (Docker Hub login)
//   aws-credentials   → AWS Credentials    (IAM Access Key + Secret Key)
//   rds-password      → Secret text        (RDS MySQL password, 8-41 ASCII chars, no / @ " space)
//   ec2-ssh-key       → SSH Username with private key (Username: ubuntu + .pem key)
//
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'PROVISION_INFRA',
            defaultValue: true,
            description: 'Create/update AWS infrastructure (VPC, Subnets, IGW, Routes, SGs, EC2, RDS MySQL, S3) via Terraform'
        )
        booleanParam(
            name: 'DESTROY_INFRA',
            defaultValue: false,
            description: 'DANGER: Destroy the AWS infrastructure managed by Terraform in infrastructure/ (skips build & deploy)'
        )
        string(
            name: 'KEY_PAIR_NAME',
            defaultValue: 'laptopkeymumhp02',
            description: 'Existing AWS EC2 Key Pair name in ap-south-1'
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

        stage('1. Clone Repository') {
            steps {
                git branch: "${GIT_BRANCH}", url: "${GIT_REPO}"
                sh 'ls -la'
            }
        }

        stage('2. Destroy Infrastructure (If Requested)') {
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
                        set -e
                        mkdir -p "\${WORKSPACE}/.tools/bin"
                        export PATH="\${WORKSPACE}/.tools/bin:\$PATH"

                        if ! command -v terraform >/dev/null 2>&1; then
                            TF_VER=\$(curl -fsSL https://checkpoint-api.hashicorp.com/v1/check/terraform | python3 -c "import json,sys; print(json.load(sys.stdin)['current_version'])")
                            curl -fsSL "https://releases.hashicorp.com/terraform/\${TF_VER}/terraform_\${TF_VER}_linux_amd64.zip" -o /tmp/tf.zip
                            python3 -m zipfile -e /tmp/tf.zip "\${WORKSPACE}/.tools/bin"
                            chmod +x "\${WORKSPACE}/.tools/bin/terraform"
                            rm -f /tmp/tf.zip
                        fi

                        export TF_VAR_key_pair_name="${params.KEY_PAIR_NAME}"
                        cd ${INFRA_DIR}
                        terraform init -input=false
                        terraform destroy -auto-approve -input=false
                    """
                }
            }
        }

        stage('3. Provision AWS Infrastructure (Terraform)') {
            when {
                expression { return params.DESTROY_INFRA == false && params.PROVISION_INFRA == true }
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
                        set -e
                        mkdir -p "\${WORKSPACE}/.tools/bin"
                        export PATH="\${WORKSPACE}/.tools/bin:\$PATH"

                        if ! command -v terraform >/dev/null 2>&1; then
                            echo "Installing Terraform into workspace tools..."
                            TF_VER=\$(curl -fsSL https://checkpoint-api.hashicorp.com/v1/check/terraform | python3 -c "import json,sys; print(json.load(sys.stdin)['current_version'])")
                            curl -fsSL "https://releases.hashicorp.com/terraform/\${TF_VER}/terraform_\${TF_VER}_linux_amd64.zip" -o /tmp/tf.zip
                            python3 -m zipfile -e /tmp/tf.zip "\${WORKSPACE}/.tools/bin"
                            chmod +x "\${WORKSPACE}/.tools/bin/terraform"
                            rm -f /tmp/tf.zip
                        fi

                        export TF_VAR_key_pair_name="${params.KEY_PAIR_NAME}"
                        cd ${INFRA_DIR}
                        terraform init -input=false
                        terraform apply -auto-approve -input=false

                        echo "EC2_PUBLIC_IP=\$(terraform output -raw ec2_public_ip)" > ../infra_outputs.env
                        echo "RDS_ADDRESS=\$(terraform output -raw rds_address)" >> ../infra_outputs.env
                        echo "S3_BUCKET_OUT=\$(terraform output -raw s3_bucket_name)" >> ../infra_outputs.env
                        cat ../infra_outputs.env
                    """
                }
            }
        }

        stage('4. Build Docker Image') {
            when {
                expression { return params.DESTROY_INFRA == false }
            }
            steps {
                sh """
                    set -e
                    docker build --no-cache \\
                        -t ${DOCKER_VERSIONED} \\
                        -t ${DOCKER_LATEST} \\
                        .
                    docker images | grep college-management
                """
            }
        }

        stage('5. Trivy Vulnerability Scan') {
            when {
                expression { return params.DESTROY_INFRA == false }
            }
            steps {
                sh """
                    set -e
                    mkdir -p "\${WORKSPACE}/.tools/bin"
                    export PATH="\${WORKSPACE}/.tools/bin:\$PATH"

                    if ! command -v trivy >/dev/null 2>&1; then
                        echo "Installing Trivy into workspace tools..."
                        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b "\${WORKSPACE}/.tools/bin"
                    fi

                    trivy --version

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

                    echo "CRITICAL vulnerabilities found: \$CRITICAL_COUNT"
                    if [ "\$CRITICAL_COUNT" -gt "0" ]; then
                        echo "PIPELINE FAILED: Critical vulnerabilities detected!"
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

        stage('6. Push to Docker Hub') {
            when {
                expression { return params.DESTROY_INFRA == false }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        set -e
                        echo "\$DOCKER_PASS" | docker login -u "\$DOCKER_USER" --password-stdin
                        docker push ${DOCKER_VERSIONED}
                        docker push ${DOCKER_LATEST}
                        docker logout
                    """
                }
            }
        }

        stage('7. Deploy & Connect Container on EC2 (RDS + S3)') {
            when {
                expression { return params.DESTROY_INFRA == false }
            }
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
                        set -e
                        export PATH="\${WORKSPACE}/.tools/bin:\$PATH"

                        TARGET_EC2="${params.EC2_HOST}"
                        TARGET_RDS="${params.RDS_HOST}"
                        TARGET_S3="${params.S3_BUCKET}"

                        if [ -f "infra_outputs.env" ]; then
                            . ./infra_outputs.env
                            [ -z "\$TARGET_EC2" ] && TARGET_EC2="\$EC2_PUBLIC_IP"
                            [ -z "\$TARGET_RDS" ] && TARGET_RDS="\$RDS_ADDRESS"
                            [ -z "\$TARGET_S3" ] && TARGET_S3="\$S3_BUCKET_OUT"
                        elif [ -f "${INFRA_DIR}/terraform.tfstate" ] && command -v terraform >/dev/null 2>&1; then
                            [ -z "\$TARGET_EC2" ] && TARGET_EC2=\$(terraform -chdir=${INFRA_DIR} output -raw ec2_public_ip 2>/dev/null || echo "")
                            [ -z "\$TARGET_RDS" ] && TARGET_RDS=\$(terraform -chdir=${INFRA_DIR} output -raw rds_address 2>/dev/null || echo "")
                            [ -z "\$TARGET_S3" ] && TARGET_S3=\$(terraform -chdir=${INFRA_DIR} output -raw s3_bucket_name 2>/dev/null || echo "")
                        fi

                        if [ -z "\$TARGET_EC2" ] || [ -z "\$TARGET_RDS" ] || [ -z "\$TARGET_S3" ]; then
                            echo "Missing EC2_HOST, RDS_HOST, or S3_BUCKET. Enable PROVISION_INFRA or provide parameters."
                            exit 1
                        fi

                        echo "Target EC2 : \$TARGET_EC2"
                        echo "Target RDS : \$TARGET_RDS"
                        echo "Target S3  : \$TARGET_S3"

                        # Wait for SSH on newly launched EC2
                        echo "Waiting for SSH on \${TARGET_EC2}..."
                        for i in \$(seq 1 24); do
                            if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "\$SSH_KEY_FILE" "\${SSH_USER}@\${TARGET_EC2}" "echo ssh-ready" >/dev/null 2>&1; then
                                break
                            fi
                            sleep 5
                        done

                        SECRET_KEY_VAL=\$(openssl rand -hex 32)
                        RDS_PASS_B64=\$(printf '%s' "\$RDS_PASSWORD" | base64 | tr -d '\\n')

                        ssh -o StrictHostKeyChecking=no -i "\$SSH_KEY_FILE" "\${SSH_USER}@\${TARGET_EC2}" \\
                            "bash -s -- '${DOCKER_VERSIONED}' '${DOCKER_LATEST}' '${CONTAINER_NAME}' '\${TARGET_RDS}' '${DB_PORT}' '${DB_NAME}' '${DB_USER}' '${AWS_REGION}' '\${TARGET_S3}' '\${SECRET_KEY_VAL}' '\${RDS_PASS_B64}'" < scripts/ec2_deploy_container.sh

                        echo "Verifying /health endpoint on http://\${TARGET_EC2}:8080/health ..."
                        HEALTHY=0
                        for i in \$(seq 1 12); do
                            CODE=\$(curl -s -o /dev/null -w "%{http_code}" "http://\${TARGET_EC2}:8080/health" || echo "000")
                            if [ "\$CODE" = "200" ]; then
                                echo "Application is LIVE and healthy at http://\${TARGET_EC2}:8080"
                                HEALTHY=1
                                break
                            fi
                            echo "Attempt \$i returned HTTP \$CODE — retrying in 5s..."
                            sleep 5
                        done

                        if [ "\$HEALTHY" -ne 1 ]; then
                            echo "Health check failed on http://\${TARGET_EC2}:8080/health"
                            exit 1
                        fi
                    """
                }
            }
        }
    }

    post {
        always {
            sh """
                docker rmi ${DOCKER_VERSIONED} 2>/dev/null || true
                docker rmi ${DOCKER_LATEST} 2>/dev/null || true
                rm -f infra_outputs.env 2>/dev/null || true
            """
        }
    }
}
