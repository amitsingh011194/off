


Claim offer

properties([
    parameters([
        choice(name: 'PLATFORM', choices: ['multi-tenant-platform'], description: 'Which Platform is the AWS account on?'),
        choice(name: 'CUSTOMER', choices: ['demo','clientdemo','mf','pra','omf','bcs','lfs','sce','nrg','nrgr'], description: 'Please choose the customer'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Enviornment you want to deploy to'),
        booleanParam(name: 'INCLUDE_JAVA_LAMBDAS', defaultValue: false, description: 'Include application/java/lambda in artifact zip?')
       // string(name: 'VERSION', defaultValue: '', description: 'Provide a specific version to deploy'),
       // booleanParam(name: 'RUN_FLYWAY', defaultValue: false, description: 'Set to true to run Flyway')
    ])
])

pipeline {
    agent  {
        label 'cicd' 
    }

    environment {
        PLATFORM="${params.PLATFORM}"
        CUSTOMER="${params.CUSTOMER}"
        ENVIRONMENT="${params.ENVIRONMENT}"
        //REGION="us-east-1"
        VERSION="${params.VERSION}"
        //RUN_FLYWAY="${params.RUN_FLYWAY}"
        //GIT_REPO_URL_TERRAFORM="https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-dgt-paymentor-core-aws-iac.git"
        GIT_REPO_URL_APPCODE="https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-paymentor-core-app.git"
        OIDC_ROLE_NAME="paymentor-oidc-role"
        DATE ="${new Date().format('yyyyMMdd')}"    
    }

    stages {
        stage('Auth Check') {
            when {
                expression { "${ENVIRONMENT}" != "dev" }
            }
            steps {
                script {
                    sh """
                        chmod +x scripts/env-protection.sh && ./scripts/env-protection.sh deploy
                    """
                }
            }
        }
        stage('Get customer mapping') {
            steps {
                script {
                     currentBuild.description = "CUSTOMER: ${env.CUSTOMER} \n BRANCH: ${env.BRANCH} \n ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"
                    // Define environment-to-account ID mapping
                    def envAccountMap = [
                        dev: '607436280417',
                        uat: '658960620175',
                        prod: '016795361898'
                    ]

                     // Get the account ID based on selected TARGET_ENV
                    env.AWS_ACCOUNT_ID = envAccountMap[params.ENVIRONMENT]
                    env.AWS_ROLE_ARN = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
                    
                    // Get TENANT_ENV and TENANT_ID from customer json file
                    env.TENANT_ENV = sh(script: "jq -r --arg env '${ENVIRONMENT}' '.[\$env].tenant_env' resources/customer-mapping/${CUSTOMER}.json", returnStdout: true).trim()
                    env.TENANT_ID = sh(script: "jq -r --arg env '${ENVIRONMENT}' '.[\$env].tenant_id' resources/customer-mapping/${CUSTOMER}.json", returnStdout: true).trim()

                    echo "Selected ENVIRONMENT: ${ENVIRONMENT}"
                    echo "Mapped AWS_ACCOUNT_ID: ${AWS_ACCOUNT_ID}"
                    echo "AWS_ROLE_ARN: ${AWS_ROLE_ARN}"
                    echo "TENANT_ID: ${TENANT_ID}"
                    echo "TENANT_ENV: ${TENANT_ENV}"
                }
            }
        }
        stage('git checkout') {
            steps {
              //  checkout([$class: 'GitSCM', branches: [[name: "main"]], extensions: [], userRemoteConfigs: [[url: "${GIT_REPO_URL_TERRAFORM}"]]])
                checkout([$class: 'GitSCM', branches: [[name: "client/${CUSTOMER}/${ENVIRONMENT}"]], extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'ApplicationCodeRepo']], userRemoteConfigs: [[url: "${GIT_REPO_URL_APPCODE}"]]])
            }
        }
        
 stage('generate artifacts') {
    steps{
        sh """
        mkdir -p output

        BASE_PATH="ApplicationCodeRepo/application"
        ZIP_FILE="output/paym-artifacts-${CUSTOMER}-${DATE}.zip"

        FILES="\$BASE_PATH/db \$BASE_PATH/lambdas"

        # Include Java lambdas if enabled
        if [ "\${INCLUDE_JAVA_LAMBDAS}" = "true" ]; then
            FILES="\$FILES \$BASE_PATH/java/lambdas"
        fi

        # Include ECS folder only if it exists
        if [ -d "\$BASE_PATH/ecs" ]; then
            echo "ECS folder found, including in zip"
            FILES="\$FILES \$BASE_PATH/ecs"
        else
            echo "ECS folder not found, skipping"
        fi

        zip -r \$ZIP_FILE \$FILES -x "*/env_vars/*" "*/README.md"
        """
    }
}

        /*
        stage('terraform plan') {
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                terraform init -no-color -backend-config="bucket=${AWS_ACCOUNT_ID}-paymentor-tf-state-mgmt" -backend-config="key=${TENANT_ENV}/${TENANT_ID}/terraform.tfstate"
                                terraform validate
                                echo ${VERSION}
                                terraform plan -no-color -out=tfplan -var "customer_id=${TENANT_ID}" -var "env_id=${TENANT_ENV}" -var "target_env=${ENVIRONMENT}" -var "paymentor_version=${VERSION}" -var-file="ApplicationCodeRepo/application_config/${ENVIRONMENT}.tfvars"
                               # terraform plan -no-color -out=tfplan -var "customer_id=${TENANT_ID}" -var "env_id=${TENANT_ENV}" -var "target_env=${ENVIRONMENT}" -var "paymentor_version=${VERSION}" -var-file="ApplicationCodeRepo/application_config/${ENVIRONMENT}.tfvars"
                            """
                         }
                    }
                }
            }
        }
    
        stage('terragrunt plan') {
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                TF_VAR_paymentor_version=${VERSION} terragrunt plan --terragrunt-working-dir multi-tenant-platform/${ENVIRONMENT}/${CUSTOMER}/${REGION}/paymentor-core
                            """
                         }
                    }
                }
            }
        }

        
        stage('Run terragrunt Apply?') {
            input {
                message 'Continue with deploy?'
                ok 'Approve'
                submitterParameter 'approverId'
            }

            steps {
                echo "Deployment approved by ${approverId}."
            }
        }
        stage('terragrunt apply') {
            when {
                expression { "${ENVIRONMENT}" != "prod" }
            }
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        sh """
                            TF_VAR_paymentor_version=${VERSION} terragrunt apply --terragrunt-working-dir multi-tenant-platform/${ENVIRONMENT}/${CUSTOMER}/${REGION}/paymentor-core
                        """
                    }
                }
            }
        }
        stage('flyway deployment') {
            when {
                expression { "${RUN_FLYWAY}" == true }
            }
            steps {
                script {
                    sh """
                        chmod -R +x scripts
                        scripts/flyway.sh
                    """
                }
            }
        }
        stage('Prod Protection') {
            when {
                expression { "${ENVIRONMENT}" == "prod" }
            }
            input {
                id 'ProductionApproval'
                message 'WARNING: You are about to deploy to PRODUCTION! This cannot be undone. Do you want to proceed?'
                ok 'Yes, Deploy to Production'
                submitterParameter 'approverId'
                parameters {
                    booleanParam(name: 'CONFIRM_DEPLOY', defaultValue: false, description: 'Check this box to confirm deployment to production')
                }
            }
            steps {
                script {
                    if (env.CONFIRM_DEPLOY != "true") {
                        error "❌ Deployment aborted: CONFIRM_DEPLOY is not set to 'true'."
                    }
                }
            }
        }
        stage('Deploy Production') {
            when {
                expression { "${ENVIRONMENT}" == "prod" }
            }
            steps {
                script {
                    echo "Deploy to prod"
                }
            }
            // steps {
            //     withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
            //         script {
            //             sh """
            //                 TF_VAR_paymentor_version=${VERSION} terragrunt apply --terragrunt-working-dir multi-tenant-platform/${ENVIRONMENT}/${CUSTOMER}/${REGION}/paymentor-core
            //             """
            //         }
            //     }
            // }
        } */
    }
    post {
        always {
            archiveArtifacts artifacts: "output/paym-artifacts-${CUSTOMER}-*.zip", fingerprint: true
        }
    }
}



currently which all folders is it zipping?

Something went wrong. If this issue persists please contact us through our help center at help.openai.com.


Retry


