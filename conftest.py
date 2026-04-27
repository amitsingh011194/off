bu-digital-paymentor-core-deploy/deploy/paymentor-whatsapp-ui
/Jenkinsfile_Promote
Go to file
t
Latest commit
binod268176
binod268176
Update Jenkinsfile_Promote
3df55cf
 · 
2 months ago
History
Breadcrumbsbu-digital-paymentor-core-deploy/deploy/paymentor-whatsapp-ui
/Jenkinsfile_Promote
File metadata and controls

Code

Blame
152 lines (137 loc) · 7.14 KB
def envAccountMap = [
    mbac: [
        dev: [account: '607436280417', region: 'us-east-1', ecrRepo: 'sb-dev12-core-1ejv3rw9q02jx-health-sns8jy9vkmsz'],
        uat: [account: '658960620175', region: 'us-east-1', ecrRepo: 'sb-utp1-core-16y7zky0tqovp-health-624devcg6n82'],
        prod: [account: '016795361898', region: 'us-east-1', ecrRepo: 'sb-prod1-core-1o4sdonwpxsh4-health-4anrjg3tczbn']
    ],
    lfs: [
        dev: [account: '116981803571', region: 'ap-southeast-2', ecrRepo: 'sb-psdev2-core-1v5ugvvbgog8d-health-bvljcgk7sxxk'],
        uat: [account: '216989139664', region: 'ap-southeast-2', ecrRepo: 'sb-psuat1-core-1cqpj3s9lylw-health-txukoparfvy4'],
        prod: [account: '767828744639', region: 'ap-southeast-2', ecrRepo: 'sb-psprod1-core-1rf31m7hkhs63-health-eof6ij9okrz2']
    ]
]

properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['mbac','lfs'], description: 'Which Customer'),
        choice(name: 'SOURCE_ENVIRONMENT', choices: ['dev','uat'], description: 'Which Environment you want to promote from'),
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Provide a specific image tag to promote', trim: true),
        booleanParam(name: 'AUTO_DEPLOY_PROMOTED_IMAGE', defaultValue: true, description: 'Auto deploy promoted image to higher environment')
    ])
])

pipeline {
    agent {
        label 'cicd'
    }

    environment {
        CUSTOMER = "${params.CUSTOMER}"
        SOURCE_ENVIRONMENT = "${params.SOURCE_ENVIRONMENT}"
        IMAGE_TAG = "${params.IMAGE_TAG}"
        ASSUME_ROLE_NAME = "paymentor-ecs-deploy"
        OLD_ASSUME_ROLE = "paymentor-oidc-role"
    }

    stages {
        stage('Get Env mapping') {
            steps {
                script {
// Set job description on Jenkins UI
                    currentBuild.description = "ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"
                    if (!params.IMAGE_TAG) error "IMAGE_TAG parameter is required!"

                    if (env.SOURCE_ENVIRONMENT == 'dev') {
                        env.DESTINATION_ENVIRONMENT = 'uat'
                    } else {
                        env.DESTINATION_ENVIRONMENT = 'prod'
                        env.ASSUME_ROLE_NAME = "${OLD_ASSUME_ROLE}"
                    }

                    echo "SOURCE_ENVIRONMENT: ${SOURCE_ENVIRONMENT}"
                    echo "DESTINATION_ENVIRONMENT: ${DESTINATION_ENVIRONMENT}"

                    env.SOURCE_AWS_ACCOUNT_ID = envAccountMap[env.CUSTOMER][env.SOURCE_ENVIRONMENT].account
                    env.SOURCE_ENVIRONMENT_ECR_REPO = envAccountMap[env.CUSTOMER][env.SOURCE_ENVIRONMENT].ecrRepo
                    env.SOURCE_AWS_ROLE_ARN = "arn:aws:iam::${SOURCE_AWS_ACCOUNT_ID}:role/${ASSUME_ROLE_NAME}"
                    env.REGION = envAccountMap[env.CUSTOMER][env.SOURCE_ENVIRONMENT].region

                    env.DESTINATION_AWS_ACCOUNT_ID = envAccountMap[env.CUSTOMER][env.DESTINATION_ENVIRONMENT].account
                    env.DESTINATION_ENVIRONMENT_ECR_REPO = envAccountMap[env.CUSTOMER][env.DESTINATION_ENVIRONMENT].ecrRepo
                    env.DESTINATION_AWS_ROLE_ARN = "arn:aws:iam::${DESTINATION_AWS_ACCOUNT_ID}:role/${OLD_ASSUME_ROLE}"

                    sh """
                        echo $REGION
                        echo $SOURCE_ENVIRONMENT
                        echo $SOURCE_AWS_ACCOUNT_ID
                        echo $SOURCE_ENVIRONMENT_ECR_REPO
                        echo $SOURCE_AWS_ROLE_ARN

                        echo DESTINATION
                        echo $DESTINATION_AWS_ACCOUNT_ID
                        echo $DESTINATION_ENVIRONMENT_ECR_REPO
                        echo $DESTINATION_AWS_ROLE_ARN
                    """
                }
            }
        }

        stage('Check image exists') {
            steps {
                withAWS(role: "${SOURCE_AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                if ! aws ecr describe-images \
                                    --repository-name ${SOURCE_ENVIRONMENT_ECR_REPO} \
                                    --image-ids imageTag=${IMAGE_TAG} \
                                    --region ${REGION} > /dev/null 2>&1; then
                                    echo "❌ Image tag: ${IMAGE_TAG} does not exist in ECR Repo: ${SOURCE_ENVIRONMENT_ECR_REPO} in Account: ${SOURCE_AWS_ACCOUNT_ID} ❌"
                                    exit 1
                                else
                                    echo "✅ Image tag: ${IMAGE_TAG} exists in ECR Repo: ${SOURCE_ENVIRONMENT_ECR_REPO} - continuing with promotion ✅"
                                fi
                            """
                        }
                    }
                }
            }
        }

        stage('Promote image') {
            steps {
                withAWS(role: "${SOURCE_AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${SOURCE_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
                                docker pull ${SOURCE_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SOURCE_ENVIRONMENT_ECR_REPO}:${IMAGE_TAG}
                                docker tag ${SOURCE_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${SOURCE_ENVIRONMENT_ECR_REPO}:${IMAGE_TAG} \
                                    ${DESTINATION_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${DESTINATION_ENVIRONMENT_ECR_REPO}:${IMAGE_TAG}
                            """
                        }
                    }
                }

                withAWS(role: "${DESTINATION_AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${DESTINATION_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
                                docker push ${DESTINATION_AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${DESTINATION_ENVIRONMENT_ECR_REPO}:${IMAGE_TAG}
                            """
                        }
                    }
                }
            }
        }

        stage('Auto Deploy to Promoted Env') {
            when {
                allOf {
                    expression { currentBuild.result != 'ABORTED' }
                    expression { params.AUTO_DEPLOY_PROMOTED_IMAGE }
                }
            }
            steps {
                echo "Triggering deployment for ${CUSTOMER} to ${DESTINATION_ENVIRONMENT} with image tag ${IMAGE_TAG}"
                build job: 'BU/Digital/Paymentor/paymentor-ui/whatsapp-ui-deploy', parameters: [
                    string(name: 'CUSTOMER', value: "${CUSTOMER}"),
                    string(name: 'ENVIRONMENT', value: "${DESTINATION_ENVIRONMENT}"),
                    string(name: 'IMAGE_TAG', value: "${IMAGE_TAG}")
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
