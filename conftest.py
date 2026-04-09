
properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['demo','fhc', 'lcc', 'fdr', 'nrg', 'nrgr', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'bcs', 'omf', 'lfs', 'clientdemo'], description: 'Which Customer do you want to deploy'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Enviornment you want to deploy to'),
        booleanParam(name: 'BUILD_JAVA_LAMBDA', defaultValue: false, description: 'Also build the Java lambda - this takes a lot of time'),
        booleanParam(name: 'RUN_DB_MIGRATION', defaultValue: false, description: 'Set to true to run Flyway'),
        booleanParam(name: 'RUN_CLI_SCRIPT', defaultValue: false, description: 'Run CLI script - Applicable for ClientDemo, DEMO, LCC, NRG, NRGR, HSBCinm, HSBCmyh Tenants!'),
        booleanParam(
        name: 'UPLOAD_NEW_IMAGE',
        defaultValue: false,
        description: 'Its not applicable for any tenant currently, please do not select it, Its only for DevOps testing at this moment'
        ),
        string(
        name: 'IMAGE_TAG',
        defaultValue: '',
        description: 'Its not applicable for any tenant currently, please do not select it, Its only for DevOps testing at this moment'
       )
        
    ])
])

pipeline {
    agent  {
        label 'cicd' 
    }

    environment {
        CUSTOMER="${params.CUSTOMER}"
        ENVIRONMENT="${params.ENVIRONMENT}"
        GIT_REPO_URL="https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-dgt-paymentor-core-aws-app.git"
        OIDC_ROLE_NAME="paymentor-oidc-role"
        IMAGE_TAG = "${env.BUILD_NUMBER}"

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
            // Set job description on Jenkins UI
            currentBuild.description = "CUSTOMER: ${env.CUSTOMER} \n ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"

            // Define environment-to-account ID mapping
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

            // Select the appropriate map based on the CUSTOMER parameter
            def selectedMap
            if (params.CUSTOMER == 'lfs') {
                selectedMap = envAccountMapLFS
            } else if (params.CUSTOMER == 'hsbcinm' || params.CUSTOMER == 'hsbcmyh') {
                selectedMap = envAccountMapHSBC
            } else if (params.CUSTOMER == 'fdr') {
                selectedMap = envAccountMapFDR
            } else {
                selectedMap = envAccountMap
            }

            // Get the account ID based on selected ENVIRONMENT
            env.AWS_ACCOUNT_ID = selectedMap[params.ENVIRONMENT]

            // ✅ NEW: Set AWS region dynamically
            if (params.CUSTOMER == 'lfs') {
                env.AWS_REGION = 'ap-southeast-2'
            } else if (params.CUSTOMER == 'fdr') {
                env.AWS_REGION = 'ca-central-1'
            } else {
                env.AWS_REGION = 'us-east-1'
            }

            // IAM Role
            env.AWS_ROLE_ARN = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
            
            // Get TENANT_ENV and TENANT_ID from customer json file
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

            script {
    env.IMAGE_TAG_FINAL = params.IMAGE_TAG?.trim()

    if (!env.IMAGE_TAG_FINAL) {
        env.IMAGE_TAG_FINAL = env.BUILD_NUMBER
    }

    echo "Final IMAGE TAG: ${env.IMAGE_TAG_FINAL}"
}

            // Logs
            echo "Selected ENVIRONMENT: ${ENVIRONMENT}"
            echo "Mapped AWS_ACCOUNT_ID: ${AWS_ACCOUNT_ID}"
            echo "AWS_ROLE_ARN: ${AWS_ROLE_ARN}"
            echo "AWS_REGION: ${AWS_REGION}"
            echo "TENANT_ID: ${TENANT_ID}"
            echo "TENANT_ENV: ${TENANT_ENV}"
        }
    }
}
       stage('Checkout App repo') {
    steps {
        script {
            sh """
                set -e

                echo "Cloning repo..."
                git clone ${GIT_REPO_URL}

                cd bu-dgt-paymentor-core-aws-app
                git checkout client/${CUSTOMER}/${ENVIRONMENT}

                echo "========================================"
                echo "Workspace inside repo after checkout:"
                echo "========================================"
                ls -l

                SRC_DIR="devops_handled_lambdas"
                DEST_DIR="application/lambdas"

                echo "========================================"
                echo "Checking for \$SRC_DIR at repo root..."
                echo "========================================"

                if [ -d "\${SRC_DIR}" ]; then
        mkdir -p "\${DEST_DIR}"
        cp -r "\${SRC_DIR}"/. "\${DEST_DIR}"/
        rm -rf "\${SRC_DIR}"
    else
        echo "Folder '\${SRC_DIR}' not found. Skipping."
    fi

                echo "========================================"
                echo "Final lambdas directory structure:"
                echo "========================================"
                ls -l "\$DEST_DIR" || true
            """
        }
    }
}


stage('ECS Build & Push') {
    when { expression { params.UPLOAD_NEW_IMAGE && params.CUSTOMER == 'lfs' } }
    steps {
        withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
            script {
                sh """
                    set -e
                    cd bu-dgt-paymentor-core-aws-app

                    pwd
                    ls -l application/ecs/

                    # Login to ECR once ✅
                    aws ecr get-login-password --region ${AWS_REGION} | \\
                    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                """

                // Define image name and folder mapping
                def images = [
                    [name: 'voice-processor', folder: 'agai_voice_processor'],
                    [name: 'voice-assistant', folder: 'agai_voice_assistant'],
                    [name: 'llm-engine', folder: 'agai-llm-engine']
                ]

                def builds = [:]

                images.each { img ->
                    builds[img.name] = {
                        sh """
                            set -e
                            cd bu-dgt-paymentor-core-aws-app

                            if [ -d "application/ecs/${img.folder}" ]; then
                                echo "Building ECS image: ${img.name}"

                                # Build image
                                docker build -t agai-${img.name}:${BUILD_NUMBER} application/ecs/${img.folder}

                                # Tag image
                                docker tag agai-${img.name}:${BUILD_NUMBER} \\
                                ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sb-${TENANT_ENV}-${TENANT_ID}-agai-${img.name}:${BUILD_NUMBER}

                                # Push image
                                docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sb-${TENANT_ENV}-${TENANT_ID}-agai-${img.name}:${BUILD_NUMBER}
                            else
                                echo "Folder application/ecs/${img.folder} not found. Skipping ${img.name}."
                            fi
                        """
                    }
                }

                parallel builds
            }
        }
    }
}
        stage('Build Java lambda') {
            when {
                allOf {
                    expression { currentBuild.result != 'ABORTED' } // Only run if not aborted
                    expression { params.BUILD_JAVA_LAMBDA }
                }
            }
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        ansiColor('xterm') {
                            sh """
                                chmod +x ./scripts/build-java-lambda.sh && ./scripts/build-java-lambda.sh
                            """
                        }
                    }
                }
            }
        }

    

        
      stage('terraform plan') {
    steps {
        withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
            script {
                ansiColor('xterm') {

                    def imageTag = params.IMAGE_TAG?.trim() ? params.IMAGE_TAG : BUILD_NUMBER
                    echo "Using image tag: ${imageTag}"

                    sh """
                        cd bu-dgt-paymentor-core-aws-app/cicd
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
        // stage('Prod Protection') {
        //     when {
        //         expression { params.ENVIRONMENT == "prod" }
        //     }
        //     input {
        //         id 'ProductionApproval'
        //         message 'WARNING: You are about to deploy to PRODUCTION! This cannot be undone. Do you want to proceed?'
        //         ok 'Yes, Deploy to Production'
        //         submitterParameter 'approverId'
        //         parameters {
        //             booleanParam(name: 'CONFIRM_DEPLOY', defaultValue: false, description: 'Check this box to confirm deployment to production')
        //         }
        //     }
        //     steps {
        //         script {
        //             if (env.CONFIRM_DEPLOY != "true") {
        //                 error "❌ Deployment aborted: CONFIRM_DEPLOY is not set to 'true'."
        //             }
        //         }
        //     }
        // }
       stage('terraform apply') {
    steps {
        withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
            script {
                ansiColor('xterm') {

                    def imageTag = params.IMAGE_TAG?.trim() ? params.IMAGE_TAG : BUILD_NUMBER

                    sh """
                        cd bu-dgt-paymentor-core-aws-app/cicd
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

        stage('Configure Pinpoint Event Destination') {
  when { expression { params.RUN_CLI_SCRIPT } }
  steps {
    withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
      script {
        def configSetName = "sb-${TENANT_ENV}-${TENANT_ID}-sms-config"
        def eventDestName = "sb-${TENANT_ENV}-${TENANT_ID}-sms-event-destination"
        def firehoseName  = "sb-${TENANT_ENV}-${TENANT_ID}-pinpoint-sms-to-s3"
        def roleArn       = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/sb-${TENANT_ENV}-${TENANT_ID}-pinpoint-event-to-firehose-role"

        echo "Fetching Firehose ARN for stream: ${firehoseName}"
        def firehoseArn = sh(
          script: "aws firehose describe-delivery-stream --delivery-stream-name ${firehoseName} --query 'DeliveryStreamDescription.DeliveryStreamARN' --output text",
          returnStdout: true
        ).trim()

        echo "Using Configuration Set: ${configSetName}"
        echo "Using Event Destination Name: ${eventDestName}"
        echo "Using Role ARN: ${roleArn}"
        echo "Using Firehose ARN: ${firehoseArn}"

        // Ensure the stream is fully ready (optional)
        sh "sleep 10"

        // Write destination JSON to avoid escape issues
        writeFile file: 'firehose-dest.json', text: """{
          "DeliveryStreamArn": "${firehoseArn}",
          "IamRoleArn": "${roleArn}"
        }"""

        // Create (or re-create) the destination
        sh """
  set -e

  echo "Checking if event destination exists..."
  EXISTS=\$(aws pinpoint-sms-voice-v2 describe-configuration-sets \
    --configuration-set-names ${configSetName} \
    --query "length(ConfigurationSets[0].EventDestinations[?EventDestinationName=='${eventDestName}'])" \
    --output text)

  if [ "\$EXISTS" = "0" ] || [ "\$EXISTS" = "None" ]; then
    echo "Event destination not found; creating..."
    aws pinpoint-sms-voice-v2 create-event-destination \
      --configuration-set-name ${configSetName} \
      --event-destination-name ${eventDestName} \
      --matching-event-types TEXT_ALL \
      --kinesis-firehose-destination file://firehose-dest.json \
      --cli-binary-format raw-in-base64-out
  else
    echo "Event destination exists; updating..."
    aws pinpoint-sms-voice-v2 update-event-destination \
      --configuration-set-name ${configSetName} \
      --event-destination-name ${eventDestName} \
      --matching-event-types TEXT_ALL \
      --kinesis-firehose-destination file://firehose-dest.json \
      --enabled
  fi
"""
      }
    }
  }
}




        stage('flyway deployment') {
            when {
                allOf {
                    expression { currentBuild.result != 'ABORTED' } // Only run if not aborted
                    expression { params.RUN_DB_MIGRATION }
                }
            }
            steps {
                withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
                    script {
                        sh """
                        chmod +x ./scripts/flyway.sh && ./scripts/flyway.sh
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
