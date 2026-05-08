properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['absa','lfs'], description: 'Which Customer'),
        string(name: 'BRANCH', defaultValue: 'absa-new', description: 'Provide branch you want to build from'),
        string(name: 'TAG_OVERRIDE', defaultValue: '', description: 'Provide a specific tag to override build number'),
        booleanParam(name: 'AUTO_DEPLOY_DEV', defaultValue: true, description: 'Auto deploy new image to Dev environment')
    ])
])

pipeline {
    agent {
        label 'cicd'
    }

    environment {
        CUSTOMER="${params.CUSTOMER}"
        BRANCH="${params.BRANCH}"
        VERSION="${params.VERSION}"
        ENVIRONMENT="dev"

        OIDC_ROLE_NAME="paymentor-oidc-role"

        REPO_NAME="bu-digital-paymentor-whatsapp-verify-number-app"
    }

    stages {

        stage('Get customer mapping') {
            steps {
                script {

                    currentBuild.description = "CUSTOMER: ${env.CUSTOMER} \n ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"

                    // Default account mappings
                    def envAccountMap = [
                        dev: '607436280417',
                        uat: '658960620175',
                        prod: '016795361898'
                    ]

                    def envAccountMapLFS = [
                        dev: '116981803571',
                        uat: '216989139664',
                        prod: '767828744639'
                    ]

                    def envAccountMapHSBC = [
                        dev: '088082905288',
                        uat: '793586321398',
                        prod: '501957928506'
                    ]

                    def envAccountMapFDR = [
                        dev: '975949451286',
                        uat: '069295248160',
                        prod: '609714460132'
                    ]

                    // ABSA mapping
                    def envAccountMapABSA = [
                        dev: '975359590581'
                    ]

                    // Select account map
                    def selectedMap

                    if (params.CUSTOMER == 'lfs') {

                        selectedMap = envAccountMapLFS

                    } else if (params.CUSTOMER == 'hsbcinm' || params.CUSTOMER == 'hsbcmyh') {

                        selectedMap = envAccountMapHSBC

                    } else if (params.CUSTOMER == 'fdr') {

                        selectedMap = envAccountMapFDR

                    } else if (params.CUSTOMER == 'absa') {

                        selectedMap = envAccountMapABSA

                    } else {

                        selectedMap = envAccountMap
                    }

                    env.AWS_ACCOUNT_ID = selectedMap[env.ENVIRONMENT]

                    // Region selection
                    if (params.CUSTOMER == 'lfs') {

                        env.AWS_REGION = 'ap-southeast-2'

                    } else if (params.CUSTOMER == 'fdr') {

                        env.AWS_REGION = 'ca-central-1'

                    } else if (params.CUSTOMER == 'absa') {

                        env.AWS_REGION = 'eu-west-2'

                    } else {

                        env.AWS_REGION = 'us-east-1'
                    }

                    // IAM Role
                    env.AWS_ROLE_ARN = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"

                    // Tenant mapping
                    env.TENANT_ENV = sh(
                        script: """
                            jq -r --arg env "${ENVIRONMENT}" '.[\$env].tenant_env' resources/customer-mapping/${CUSTOMER}.json
                        """,
                        returnStdout: true
                    ).trim()

                    env.TENANT_ID = sh(
                        script: """
                            jq -r --arg env "${ENVIRONMENT}" '.[\$env].tenant_id' resources/customer-mapping/${CUSTOMER}.json
                        """,
                        returnStdout: true
                    ).trim()

                    // ECR Repo Name
                    env.ECR_REPO_NAME = "sb-${TENANT_ENV}-${TENANT_ID}-whatsapp_service_ui"

                    // Final image tag
                    env.IMAGE_TAG_FINAL = params.TAG_OVERRIDE ?: env.BUILD_NUMBER

                    // Logs
                    echo "Selected ENVIRONMENT: ${ENVIRONMENT}"
                    echo "Mapped AWS_ACCOUNT_ID: ${AWS_ACCOUNT_ID}"
                    echo "AWS_ROLE_ARN: ${AWS_ROLE_ARN}"
                    echo "AWS_REGION: ${AWS_REGION}"
                    echo "TENANT_ID: ${TENANT_ID}"
                    echo "TENANT_ENV: ${TENANT_ENV}"
                    echo "ECR_REPO_NAME: ${ECR_REPO_NAME}"
                    echo "FINAL IMAGE TAG: ${IMAGE_TAG_FINAL}"
                }
            }
        }

        stage('Checkout App repo') {
            steps {
                script {
                    sh """
                        git clone https://ucgithub.exlservice.com/Unified-Cloud-DevOps/${REPO_NAME}

                        cd ${REPO_NAME}
                        git checkout ${BRANCH}

                        ls -l
                    """
                }
            }
        }

        stage('Docker Build & Push') {
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {

                    script {

                        sh """
                            set -e

                            echo "Building docker image with tag ${IMAGE_TAG_FINAL}"

                            cd ${REPO_NAME}

                            docker build --no-cache \
                              -f Dockerfile \
                              -t ${REPO_NAME}-${IMAGE_TAG_FINAL} .

                            docker tag ${REPO_NAME}-${IMAGE_TAG_FINAL} \
                              ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sb-psdev-d37f6745-whatsapp_service_ui:${IMAGE_TAG_FINAL}

                            aws ecr get-login-password --region ${AWS_REGION} | \
                            docker login --username AWS --password-stdin \
                              ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

                            docker push \
                              ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sb-psdev-d37f6745-whatsapp_service_ui:${IMAGE_TAG_FINAL}
                        """
                    }
                }
            }
        }

        stage('terraform plan') {
            steps {

                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {

                    script {

                        ansiColor('xterm') {

                            echo "Using FINAL image tag: ${IMAGE_TAG_FINAL}"

                            sh """
                                cd ${REPO_NAME}/cicd

                                terraform init -upgrade \
                                  -backend-config="bucket=${AWS_ACCOUNT_ID}-paymentor-tf-state-mgmt" \
                                  -backend-config="key=${TENANT_ENV}/${TENANT_ID}/terraform.tfstate"

                                terraform validate

                                terraform plan -out=tfplan \
                                  -var "customer_id=${TENANT_ID}" \
                                  -var "image_tag=${IMAGE_TAG_FINAL}" \
                                  -var "env_id=${TENANT_ENV}" \
                                  -var "target_env=${ENVIRONMENT}" \
                                  -var-file="tfvars/${ENVIRONMENT}.tfvars"
                            """
                        }
                    }
                }
            }
        }

        stage('Run terraform Apply?') {

            input {
                message 'Continue with deploy?'
                ok 'Approve'
                submitter "${env.BUILD_USER_ID}"
            }

            steps {
                echo "Deployment approved by ${env.BUILD_USER_ID}."
            }
        }

        stage('terraform apply') {

            steps {

                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {

                    script {

                        ansiColor('xterm') {

                            echo "Applying with IMAGE TAG: ${IMAGE_TAG_FINAL}"

                            sh """
                                cd ${REPO_NAME}/cicd

                                terraform apply -input=false -auto-approve \
                                  -var "customer_id=${TENANT_ID}" \
                                  -var "image_tag=${IMAGE_TAG_FINAL}" \
                                  -var "env_id=${TENANT_ENV}" \
                                  -var "target_env=${ENVIRONMENT}" \
                                  -var-file="tfvars/${ENVIRONMENT}.tfvars"
                            """
                        }
                    }
                }
            }
        }

        stage('Auto Deploy to Dev') {

            when {

                allOf {

                    expression { currentBuild.result != 'ABORTED' }

                    expression { params.AUTO_DEPLOY_DEV }
                }
            }

            steps {

                build job: 'BU/Digital/Paymentor/paymentor-ui/whatsapp-ui-deploy',
                parameters: [
                    string(name: 'CUSTOMER', value: "${CUSTOMER}"),
                    string(name: 'ENVIRONMENT', value: "dev"),
                    string(name: 'IMAGE_TAG', value: "${env.IMAGE_TAG_FINAL}")
                ]
            }
        }
    }

    post {

        always {

            deleteDir()
        }
    }
}
