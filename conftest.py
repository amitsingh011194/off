properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['bcs', 'lcc', 'fdr', 'nrg', 'demo', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'mf','pra', 'mbac', 'nrgr', 'omf', 'lfs', 'clientdemo'], description: 'Customer'),
    choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Environment'),
    string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'AWS region')
  ])
])

pipeline {
  agent { label 'cicd' }

  environment {
    CUSTOMER        = "${params.CUSTOMER}"
    ENVIRONMENT     = "${params.ENVIRONMENT}"
    AWS_REGION      = "${params.AWS_REGION}"
    OIDC_ROLE_NAME  = "paymentor-oidc-role"
  }

  stages {

    stage('Get AWS Account Mapping') {
      steps {
        script {
          def envAccountMap = [
            dev:  '607436280417',
            uat:  '658960620175',
            prod: '016795361898'
          ]

          def envAccountMapLFS = [
            dev:  '116981803571',
            uat:  '216989139664',
            prod: '767828744639'
          ]

          def envAccountMapHSBC = [
            dev:  '088082905288',
            uat:  '793586321398',
            prod: '501957928506'
          ]

          def selectedMap =
            (CUSTOMER == 'lfs') ? envAccountMapLFS :
            (CUSTOMER in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
            envAccountMap

          env.AWS_ACCOUNT_ID = selectedMap[ENVIRONMENT]
          env.AWS_ROLE_ARN   = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"

          // ✅ Better Lambda naming (customer + env)
          env.LAMBDA_NAME = "${CUSTOMER}-${ENVIRONMENT}-sms-cost-monitor"

          echo "AWS_ACCOUNT_ID : ${AWS_ACCOUNT_ID}"
          echo "AWS_ROLE_ARN   : ${AWS_ROLE_ARN}"
          echo "LAMBDA_NAME    : ${LAMBDA_NAME}"
        }
      }
    }

    stage('Package Lambda') {
      steps {
        sh '''
          set -e

          echo "Packaging Lambda..."
          zip -j deploy/devOps_lambdas/function.zip deploy/devOps_lambdas/lambda_function.py

          echo "Verifying package..."
          ls -l deploy/devOps_lambdas
        '''
      }
    }

    stage('Deploy Lambda') {
      steps {
        withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
          sh '''
            set -e

            FUNCTION_NAME=${LAMBDA_NAME}

            echo "Deploying Lambda: $FUNCTION_NAME"

            if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION >/dev/null 2>&1; then
              echo "Lambda exists. Updating..."

              aws lambda update-function-code \
                --function-name $FUNCTION_NAME \
                --zip-file fileb://deploy/devOps_lambdas/function.zip \
                --region $AWS_REGION

            else
              echo "Lambda does not exist. Creating..."

              aws lambda create-function \
                --function-name $FUNCTION_NAME \
                --runtime python3.11 \
                --role arn:aws:iam::$AWS_ACCOUNT_ID:role/sms-cost-monitor-role \
                --handler lambda_function.lambda_handler \
                --zip-file fileb://deploy/devOps_lambdas/function.zip \
                --timeout 30 \
                --region $AWS_REGION
            fi
          '''
        }
      }
    }

  }

  post {
    always {
      echo "Pipeline execution completed"
      deleteDir()
    }
  }
}

lets add a stage in this for the 3rd and the 4th poin
