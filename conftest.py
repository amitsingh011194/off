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

          // Lambda name (must match Terraform-created one OR adjust if needed)
          env.LAMBDA_NAME = "sb-prod3-3878909f-service_limit_lambdas"

          echo "AWS_ACCOUNT_ID : ${AWS_ACCOUNT_ID}"
          echo "AWS_ROLE_ARN   : ${AWS_ROLE_ARN}"
          echo "LAMBDA_NAME    : ${LAMBDA_NAME}"
        }
      }
    }

stage('Invoke Lambda & Fetch Logs') {
  steps {
    withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
      script {
        sh '''
          set -e

          FUNCTION_NAME=${LAMBDA_NAME}

          echo "Invoking Lambda: $FUNCTION_NAME"

          # Invoke Lambda and capture response + logs
          aws lambda invoke \
            --function-name $FUNCTION_NAME \
            --region $AWS_REGION \
            --log-type Tail \
            output.json > lambda_output.txt

          echo "Lambda invocation completed"

          echo "========================================"
          echo "📦 Lambda Response:"
          cat output.json
          echo ""

          echo "========================================"
          echo "📜 Lambda Logs (Decoded):"

          # Extract and decode logs
          LOG_RESULT=$(cat lambda_output.txt | jq -r '.LogResult')

          if [ "$LOG_RESULT" != "null" ]; then
            echo $LOG_RESULT | base64 --decode
          else
            echo "No logs returned"
          fi

          echo "========================================"
        '''
      }
    }
  }
}
stage('Send Cost Alert Email') {
  steps {
    script {
      // Read Lambda output
      def response = readJSON file: 'output.json'
      def body = response.body

      def tenant = body.tenant
      def totalSpend = body.total_spend
      def usage = body.usage_percent
      def services = body.services

      // Build service breakdown HTML
      def serviceTable = ""
      services.each { key, value ->
        serviceTable += "<tr><td>${key}</td><td>$${value}</td></tr>"
      }

      def emailBody = """
        <h2>📊 SMS Cost Monitoring Report</h2>

        <p><b>Tenant:</b> ${tenant}</p>
        <p><b>Total Spend:</b> $${totalSpend}</p>
        <p><b>Usage:</b> ${usage}%</p>

        <h3>Service Breakdown</h3>
        <table border="1" cellpadding="5" cellspacing="0">
          <tr>
            <th>Service</th>
            <th>Cost (USD)</th>
          </tr>
          ${serviceTable}
        </table>

        <br/>
        <p><i>Generated from Jenkins Pipeline</i></p>
      """

      // 🚨 Send only if threshold exceeded
      if (usage >= 70) {
        emailext(
          to: "${env.EMAIL_RECIPIENTS}",
          subject: "🚨 SMS Cost Alert - ${tenant}",
          body: emailBody,
          mimeType: 'text/html'
        )
      } else {
        echo "Usage below threshold (${usage}%). Email not sent."
      }
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

This is how the jenkins file looks like now
