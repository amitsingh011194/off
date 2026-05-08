
properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['core','sam','dmo','chc','fhc', 'lcc', 'fdr', 'nrg', 'nrgr', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'bcs', 'omf', 'lfs', 'clientdemo'], description: 'Which Customer do you want to deploy'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Enviornment you want to deploy to'),
        booleanParam(name: 'BUILD_JAVA_LAMBDA', defaultValue: false, description: 'Also build the Java lambda - this takes a lot of time'),
        booleanParam(name: 'RUN_DB_MIGRATION', defaultValue: false, description: 'Set to true to run Flyway'),
        booleanParam(name: 'RUN_CLI_SCRIPT', defaultValue: false, description: 'Run CLI script - Applicable for ClientDemo, core, LCC, NRG, NRGR, HSBCinm, HSBCmyh Tenants!'),
        booleanParam(
        name: 'UPLOAD_NEW_IMAGE',
        defaultValue: false,
        description: 'Only for LFS tenant. Supported in DEV environment only. For UAT/PROD image push, use the promote pipeline.'
        ),
        string(
        name: 'IMAGE_TAG',
        defaultValue: '',
        description: 'Provide a specific tag to override build number - This should only be selected during the failover or rollback - Only applicable for LFS currently'
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


stage('Validate Inputs') {
    steps {
        script {
            if (
                params.UPLOAD_NEW_IMAGE &&
                !(
                    params.ENVIRONMENT == 'dev' ||
                    (params.ENVIRONMENT == 'uat' && params.CUSTOMER == 'dmo')
                )
            ) {
                error("""
UPLOAD_NEW_IMAGE is allowed only for:
- DEV environment (all tenants)
- UAT environment ONLY for tenant: dmo

For UAT/PROD (other tenants), use the promote pipeline:
https://ucjenkinsdev.exlservice.com/job/BU/job/Digital/job/Paymentor/job/paymentor-base/job/promote_docker_image/

How to deploy to UAT/PROD:
1. Use the promote pipeline to push the image to the target environment
2. Come back to this pipeline
3. Run it WITHOUT providing IMAGE_TAG
   → It will automatically pick and deploy the latest available image

Note:
- Promote pipeline only pushes images
- Deployment is handled by this pipeline
""")
            }
        }
    }
}

stage('Get customer mapping') {
    steps {
        script {
            // Set job description
            currentBuild.description = "CUSTOMER: ${env.CUSTOMER} \n ENVIRONMENT: ${env.ENVIRONMENT} \n BUILT BY: ${env.BUILD_USER_ID}"

            // Account mappings
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

            // Select account map
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

            env.AWS_ACCOUNT_ID = selectedMap[params.ENVIRONMENT]

            // Region selection
            if (params.CUSTOMER == 'lfs') {
                env.AWS_REGION = 'ap-southeast-2'
            } else if (params.CUSTOMER == 'fdr') {
                env.AWS_REGION = 'ca-central-1'
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

            // 🔥 IMAGE TAG RESOLUTION (FINAL SAFE VERSION)
            if (params.UPLOAD_NEW_IMAGE) {
                env.IMAGE_TAG_FINAL = env.BUILD_NUMBER
                echo "Using NEW image tag (build number): ${env.IMAGE_TAG_FINAL}"

            } else if (params.IMAGE_TAG?.trim()) {
                env.IMAGE_TAG_FINAL = params.IMAGE_TAG
                echo "Using PROVIDED image tag: ${env.IMAGE_TAG_FINAL}"

            } else {
                echo "Attempting to fetch latest image tag from ECR..."

                def fetchedTag = ""

           withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
   fetchedTag = sh(
    script: """
        aws ecr describe-images \
          --repository-name sb-${TENANT_ENV}-${TENANT_ID}-agai-voice-processor \
          --region ${AWS_REGION} \
          --query "imageDetails[?imageTags!=null].imageTags[]" \
          --output text | tr '\\t' '\\n' | grep -v latest | sort -nr | head -n 1
    """,
    returnStdout: true
).trim()
}

                if (!fetchedTag || fetchedTag == "None") {
                    echo "⚠️ ECR repo not found or no images exist. Falling back to BUILD_NUMBER"
                    env.IMAGE_TAG_FINAL = env.BUILD_NUMBER
                } else {
                    env.IMAGE_TAG_FINAL = fetchedTag
                    echo "Using LATEST ECR image tag: ${env.IMAGE_TAG_FINAL}"
                }
            }

            // Logs
            echo "Selected ENVIRONMENT: ${ENVIRONMENT}"
            echo "Mapped AWS_ACCOUNT_ID: ${AWS_ACCOUNT_ID}"
            echo "AWS_ROLE_ARN: ${AWS_ROLE_ARN}"
            echo "AWS_REGION: ${AWS_REGION}"
            echo "TENANT_ID: ${TENANT_ID}"
            echo "TENANT_ENV: ${TENANT_ENV}"
            echo "FINAL IMAGE TAG: ${IMAGE_TAG_FINAL}"
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
  when {
    expression { 
        params.UPLOAD_NEW_IMAGE &&
        (
            params.ENVIRONMENT == 'dev' ||
            (params.ENVIRONMENT == 'uat' && params.CUSTOMER == 'dmo')
        ) &&
        !params.IMAGE_TAG?.trim()
    }
}
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

                // Sequential execution 👇
                images.each { img ->
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

                    echo "Using FINAL image tag: ${IMAGE_TAG_FINAL}"

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

                    echo "Applying with IMAGE TAG: ${IMAGE_TAG_FINAL}"

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




You see what we are doing here? I need you to make the conditions accordingly here for the ECS Builds and all that..
Like see what we are doing in this:

 booleanParam(
        name: 'UPLOAD_NEW_IMAGE',
        defaultValue: false,
        description: 'Only for LFS tenant. Supported in DEV environment only. For UAT/PROD image push, use the promote pipeline.'
        ),


        and when this is on, we dont have to run the image build stage..


        something like this...
