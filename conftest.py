lets start one by one..
lets update the this file first:
deploy/paymentor-whatsapp-ui/Jenkinsfile_Build


def envAccountMap = [
                        mbac: [
                            dev: [account: '607436280417', region: 'us-east-1', ecrRepo: 'sb-dev12-core-1ejv3rw9q02jx-health-sns8jy9vkmsz']
                        ],
                        lfs: [
                            dev: [account: '116981803571', region: 'ap-southeast-2', ecrRepo: 'sb-psdev2-core-1v5ugvvbgog8d-health-bvljcgk7sxxk']
                            ]
                    ]


properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['mbac','lfs','absa'], description: 'Which Customer'),
        string(name: 'BRANCH', defaultValue: 'main', description: 'Provide branch you want to build from'),
        string(name: 'TAG_OVERRIDE', defaultValue: '', description: 'Provide a specific tag to override build number'),
        booleanParam(name: 'AUTO_DEPLOY_DEV', defaultValue: true, description: 'Auto deploy new image to Dev environment')
    ])
])

pipeline {
    agent  {
        label 'cicd' 
    }

    environment {
        CUSTOMER="${params.CUSTOMER}"
        BRANCH="${params.BRANCH}"
        VERSION="${params.VERSION}"
        ENVIRONMENT="dev"
        ASSUME_ROLE_NAME="paymentor-ecs-deploy"
        REPO_NAME="bu-digital-paymentor-whatsapp-verify-number-app"
    }

    stages {
        stage('Get Env mapping') {
            steps {
                script {
// Set job description on Jenkins UI
                    currentBuild.description = "ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"
                    // Get the account ID based on selected TARGET_ENV
                    env.AWS_ACCOUNT_ID = envAccountMap[env.CUSTOMER][env.ENVIRONMENT].account
                    env.REGION= envAccountMap[env.CUSTOMER][env.ENVIRONMENT].region
                    env.ECR_REPO_NAME = envAccountMap[env.CUSTOMER][env.ENVIRONMENT].ecrRepo
                    env.AWS_ROLE_ARN = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ASSUME_ROLE_NAME}"

                    sh """
                        echo $CUSTOMER
                        echo $REGION
                        echo $ECR_REPO_NAME
                        echo $AWS_ROLE_ARN
                    """
                }
            }
        }
        stage('Checkout App repo') {
            steps {
                script {
                    sh """
                        git clone https://ucgithub.exlservice.com/Unified-Cloud-DevOps/${REPO_NAME}
                        (cd ${REPO_NAME} && git checkout ${BRANCH})
                        ls -l
                    """
                }
            }
        }
        stage('Docker build') {
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        env.IMAGE_TAG = params.TAG_OVERRIDE ?: env.BUILD_NUMBER
                        sh """
                            echo "Tagging image with ${IMAGE_TAG}"

                            cd ${REPO_NAME}
                            docker build --no-cache -f Dockerfile -t ${REPO_NAME}-${IMAGE_TAG} .
                            
                            docker tag ${REPO_NAME}-${IMAGE_TAG} \
                                ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${env.ECR_REPO_NAME}:${IMAGE_TAG}
                            
                            aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${env.AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
                            docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${env.ECR_REPO_NAME}:${IMAGE_TAG}                        
                        """
                    }
                }
            }
        }
        stage('Auto Deploy to Dev') {
            when {
                allOf {
                    expression { currentBuild.result != 'ABORTED' } // Only run if not aborted
                    expression { params.AUTO_DEPLOY_DEV }
                }
            }
            steps {
                build job: 'BU/Digital/Paymentor/paymentor-ui/whatsapp-ui-deploy', parameters: [string(name: 'CUSTOMER', value: "${CUSTOMER}"), string(name: 'ENVIRONMENT', value: "dev"), string(name: 'IMAGE_TAG', value: "${env.IMAGE_TAG}" )]
            }
        }
    }
    post {
        always {
            deleteDir()
        }
    }
}
