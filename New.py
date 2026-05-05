properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['demo','dmo','chc','fhc', 'lcc', 'fdr', 'nrg', 'nrgr', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'bcs', 'omf', 'lfs', 'clientdemo'], description: 'Which Customer do you want to deploy'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Enviornment you want to deploy to'),
        booleanParam(name: 'BUILD_JAVA_LAMBDA', defaultValue: false, description: 'Also build the Java lambda - this takes a lot of time'),
        booleanParam(name: 'RUN_DB_MIGRATION', defaultValue: false, description: 'Set to true to run Flyway'),
        booleanParam(name: 'RUN_CLI_SCRIPT', defaultValue: false, description: 'Run CLI script - Applicable for ClientDemo, DEMO, LCC, NRG, NRGR, HSBCinm, HSBCmyh Tenants!'),
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
            if (params.UPLOAD_NEW_IMAGE && params.ENVIRONMENT != 'dev') {
                error("""
UPLOAD_NEW_IMAGE is allowed only for DEV environment.

To promote images to UAT/PROD, use the promote pipeline:
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


I need help with the "validate input" stage.
Could you please allow that stage to run for UAT env only if the tenant is dmo
