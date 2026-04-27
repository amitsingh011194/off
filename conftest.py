Build pipeline:
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

Deploy pipeline:
def envAccountMap = [
    mbac: [
        dev: [account: '607436280417', region: 'us-east-1', ecrRepo: 'sb-dev12-core-1ejv3rw9q02jx-health-sns8jy9vkmsz', ecsCluster: 'sb-dev12-tenant-ecs-9b342d30', ecsService: 'whatsapp-ui-service'],
        uat: [account: '658960620175', region: 'us-east-1', ecrRepo: 'sb-utp1-core-16y7zky0tqovp-health-624devcg6n82' , ecsCluster: 'sb-utp1-tenant-ecs-d2bbdd3d', ecsService: 'whatsapp-ui-service'],
        prod: [account: '016795361898', region: 'us-east-1', ecrRepo: 'sb-prod1-core-1o4sdonwpxsh4-health-4anrjg3tczbn' , ecsCluster: 'sb-prod1-tenant-ecs-801fa705', ecsService: 'whatsapp-ui-service']
    ],
    lfs: [
        dev: [account: '116981803571', region: 'ap-southeast-2', ecrRepo: 'sb-psdev2-core-1v5ugvvbgog8d-health-bvljcgk7sxxk', ecsCluster: 'sb-psdev2-tenant-ecs-0b9850d0', ecsService: 'whatsapp_service_ui'],
        uat: [account: '216989139664', region: 'ap-southeast-2', ecrRepo: 'sb-psuat1-core-1cqpj3s9lylw-health-txukoparfvy4' , ecsCluster: 'sb-psuat1-tenant-ecs-7f0e6184', ecsService: 'whatsapp_service_ui'],
        prod: [account: '767828744639', region: 'ap-southeast-2', ecrRepo: 'sb-psprod1-core-1rf31m7hkhs63-health-eof6ij9okrz2' , ecsCluster: 'sb-psprod1-tenant-3a5c0629', ecsService: 'whatsapp_service_ui']
    ]
]

properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['mbac','lfs','absa'], description: 'Select the customer'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Select the environment'),
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Docker image tag to deploy', trim: true)
    ])
])

pipeline {
    agent { label 'cicd' }

    environment {
        CUSTOMER = "${params.CUSTOMER}"
        ENVIRONMENT = "${params.ENVIRONMENT}"
        IMAGE_TAG = "${params.IMAGE_TAG}"
        ASSUME_ROLE_NAME = "paymentor-ecs-deploy"
        TASK_TEMPLATE_FILENAME = "resources/ecs-task/whatsapp-ui/${CUSTOMER}/${ENVIRONMENT}/task-definition.json"
    }

    stages {
        stage('Get Env mapping') {
            steps {
                script {
                    currentBuild.description = "CUSTOMER: ${env.CUSTOMER} \n ENVIRONMENT: ${env.ENVIRONMENT} \n IMAGE_TAG: ${env.IMAGE_TAG} \n BUILT BY: ${env.BUILD_USER_ID}"
                    if (!IMAGE_TAG) error "IMAGE_TAG is required to deploy."

                    env.AWS_ACCOUNT_ID = envAccountMap[CUSTOMER][ENVIRONMENT].account
                    env.REGION = envAccountMap[CUSTOMER][ENVIRONMENT].region
                    env.ECR_REPO_NAME = envAccountMap[CUSTOMER][ENVIRONMENT].ecrRepo
                    env.ECS_CLUSTER = envAccountMap[CUSTOMER][ENVIRONMENT].ecsCluster
                    env.ECS_SERVICE = envAccountMap[CUSTOMER][ENVIRONMENT].ecsService
                    env.AWS_ROLE_ARN = "arn:aws:iam::${env.AWS_ACCOUNT_ID}:role/${ASSUME_ROLE_NAME}"
                     
                      sh """
                        echo $CUSTOMER
                        echo $REGION
                        echo $ECR_REPO_NAME
                        echo $AWS_ROLE_ARN
                        echo $ECS_CLUSTER
                        echo $ECS_SERVICE
                    """

                }
            }
        }

     stage('Check Image Exists') {
    steps {
        withAWS(role: "${env.AWS_ROLE_ARN}", region: "${env.REGION}", useNode: true) {
            script {
                echo "Fetching all image tags from ECR repo: ${ECR_REPO_NAME}..."
                sh """
                    aws ecr list-images \
                      --repository-name ${ECR_REPO_NAME} \
                      --region ${REGION} \
                      --query 'imageIds[*].imageTag' \
                      --output text
                """

                def result = sh(
                    script: """
                        aws ecr describe-images \
                          --repository-name ${ECR_REPO_NAME} \
                          --image-ids imageTag=${IMAGE_TAG} \
                          --region ${REGION} > /dev/null 2>&1
                    """, returnStatus: true)

                if (result != 0) {
                    error "Image ${IMAGE_TAG} not found in ${ECR_REPO_NAME}"
                } else {
                    echo "Image ${IMAGE_TAG} found in ${ECR_REPO_NAME}"
                }

                echo "Attempting to fetch attached policies for role: ${AWS_ROLE_ARN}..."

                // Extract role name from ARN
                def roleName = AWS_ROLE_ARN.tokenize('/').last()

                sh """
                    aws iam list-attached-role-policies \
                      --role-name ${roleName} \
                      --region ${REGION} \
                      --output table || echo 'Failed to retrieve policies. Ensure IAM permissions allow this.'
                """
            }
        }
    }
}


        stage('Prepare Task Definition') {
            steps {
                script {
                    echo "Preparing ECS task definition from ${TASK_TEMPLATE_FILENAME}"

                    sh """
                        cp ${TASK_TEMPLATE_FILENAME} task-definition-updated.json
                        sed -i "s|IMAGE_TAG_PLACEHOLDER|${IMAGE_TAG}|" task-definition-updated.json
                        echo "Replaced image tag in task definition:"
                        grep image task-definition-updated.json
                    """
                }
            }
        }

       stage('Register Task Definition') {
            steps {
                withAWS(role: "${env.AWS_ROLE_ARN}", region: "${env.REGION}", useNode: true) {
                    script {
                        def revision = sh(
                        script: """
                            aws ecs register-task-definition \
                            --cli-input-json file://task-definition-updated.json \
                            --query 'taskDefinition.revision' \
                            --output text
                        """,
                        returnStdout: true
                        ).trim()

                        echo "Registered ECS Task Definition Revision: ${revision}"

                        // Extract the family name for the next stage
                        def json = readJSON(file: 'task-definition-updated.json')
                        env.TASK_FAMILY = json.family
                        env.TASK_REVISION = "${env.TASK_FAMILY}:${revision}"
                    }
                }
            }
        }

        
        stage('Update ECS Service') {
            steps {
                withAWS(role: "${env.AWS_ROLE_ARN}", region: "${env.REGION}", useNode: true) {
                    script {
                     

                        echo "Updating ECS Service: ${ECS_SERVICE} in Cluster: ${ECS_CLUSTER} with Task Definition: ${env.TASK_REVISION}"
                        sh """
                            aws ecs update-service \
                              --cluster ${ECS_CLUSTER} \
                              --service ${ECS_SERVICE} \
                              --task-definition ${env.TASK_REVISION} \
                              --force-new-deployment
                        """
                    }
                }
            }
        } 
    }

    post {
        always {
            deleteDir()
        }
    }
}
