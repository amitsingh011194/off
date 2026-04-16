properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','mf','pra','mbac','nrgr','omf','lfs','clientdemo']),
    choice(name: 'ENVIRONMENT', choices: ['prod','uat','dev']),
    string(name: 'AWS_REGION', defaultValue: 'us-east-1'),
    booleanParam(name: 'RUN_ALL', defaultValue: true, description: 'Run for all customers (cron mode)')
  ])
])

pipeline {
  agent { label 'cicd' }

  triggers {
    cron('H H */7 * *')  // every 30 mins (for testing)
  }

  environment {
    OIDC_ROLE_NAME   = "paymentor-oidc-role"
    EMAIL_RECIPIENTS = "amit.singh8@exlservice.com"
  }

  stages {

    stage('Process Tenants') {
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

          // 🔹 All customers list
          def TARGETS = [
            [env: 'prod', customer: 'tdb'],
            [env: 'prod', customer: 'lcc'],
            [env: 'prod', customer: 'fdr'],
            [env: 'prod', customer: 'nrg'],
            [env: 'prod', customer: 'demo'],
            [env: 'prod', customer: 'bcs'],
            [env: 'prod', customer: 'hsbcinm'],
            [env: 'prod', customer: 'hsbcmyh'],
            [env: 'prod', customer: 'sce'],
            [env: 'prod', customer: 'mf'],
            [env: 'prod', customer: 'pra'],
            [env: 'prod', customer: 'mbac'],
            [env: 'prod', customer: 'nrgr'],
            [env: 'prod', customer: 'omf'],
            [env: 'prod', customer: 'lfs'],
            [env: 'prod', customer: 'clientdemo']
          ]

          // 🔹 Decide execution mode
          def executionList = []

          if (params.RUN_ALL) {
            echo "Running in FULL mode (cron)"
            executionList = TARGETS
          } else {
            echo "Running in SINGLE mode (manual)"
            executionList.add([env: params.ENVIRONMENT, customer: params.CUSTOMER])
          }

          // 🔁 Loop
          for (t in executionList) {

            def customer = t.customer
            def envName  = t.env

            echo "=================================="
            echo "Processing ${customer} - ${envName}"
            echo "=================================="

            try {

              // 🔹 Resolve Mapping
              def mappingFile = "resources/customer-mapping/${customer}.json"

              if (!fileExists(mappingFile)) {
                echo "❌ Mapping not found for ${customer}, skipping..."
                continue
              }

              def mapping = readJSON file: mappingFile

              if (!mapping.containsKey(envName)) {
                echo "❌ Env not found in mapping, skipping..."
                continue
              }

              def tenantShort = mapping[envName].tenant_id
              def tenantEnv   = mapping[envName].tenant_env

              env.CLIENT_NAME  = customer.toUpperCase()
              env.ENV_NAME     = envName.toUpperCase()
              env.TENANT_SHORT = tenantShort
              env.TENANT_ENV   = tenantEnv

              // 🔹 Account mapping
              def selectedMap =
                (customer == 'lfs') ? envAccountMapLFS :
                (customer in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                envAccountMap

              env.AWS_ACCOUNT_ID = selectedMap[envName]
              env.AWS_ROLE_ARN   = "arn:aws:iam::${env.AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
              env.LAMBDA_NAME    = "sb-prod3-3878909f-service_limit_lambdas"

              // 🔹 Invoke Lambda
              withAWS(role: "${env.AWS_ROLE_ARN}", useNode: true) {
                sh '''
                  set -e

                  echo "Invoking Lambda: ${LAMBDA_NAME}"
                  echo "Tenant Prefix: ${TENANT_SHORT}"

                  printf '{"tenant_prefix":"%s"}' "${TENANT_SHORT}" > payload.json

                  aws lambda invoke \
                  --function-name $LAMBDA_NAME \
                  --region $AWS_REGION \
                  --cli-binary-format raw-in-base64-out \
                  --payload file://payload.json \
                  --log-type Tail \
                  output.json > lambda_output.txt

                  echo "========================================"
                  echo "📜 Lambda Logs (Decoded):"

                  LOG_RESULT=$(cat lambda_output.txt | jq -r '.LogResult')

                  if [ "$LOG_RESULT" != "null" ]; then
                    echo $LOG_RESULT | base64 --decode | tee decoded_logs.txt
                  else
                    echo "No logs returned"
                  fi

                  echo "========================================"
                '''
              }

              // 🔹 Email Stage (unchanged)
              if (!fileExists('output.json')) {
                echo "No output.json, skipping email"
                continue
              }

              def lambdaResponse = readJSON file: 'output.json'

              def body = [:]
              if (lambdaResponse.body instanceof String) {
                body = readJSON text: lambdaResponse.body
              } else if (lambdaResponse.body instanceof Map) {
                body = lambdaResponse.body
              }

              def tenant = body.tenant ?: env.TENANT_SHORT
              def totalSpend = body.total_spend ?: 0
              def usage      = body.usage_percent ?: 0

              def serviceTable = ''
              if (fileExists('decoded_logs.txt')) {

                def lines = readFile('decoded_logs.txt').split('\n')

                lines.each { line ->
                  if (line.contains('→ $')) {

                    def parts = line.split('→')
                    def service = parts[0].trim()
                    def cost = parts[1].replace('$','').trim()

                    def color = cost.toDouble() > 10 ? 'red' : (cost.toDouble() > 1 ? 'orange' : 'black')

                    serviceTable += """
<tr>
<td>${service}</td>
<td><b style="color:${color}">${'$'}${cost}</b></td>
</tr>
                    """
                  }
                }
              }

              def emailBody = '''
<h2 style="color:#2E86C1;">📊 SMS Cost Monitoring</h2>

<p><b>Tenant:</b> %TENANT%</p>
<p><b>Total Spend:</b> <span style="color:red;">$%TOTAL%</span></p>
<p><b>Usage:</b> %USAGE%%</p>

<h3>💰 Service Breakdown</h3>

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
<tr style="background-color:#f2f2f2;">
<th>Service</th>
<th>Cost ($)</th>
</tr>
%TABLE%
</table>

<br/>
<p><i>Generated from Jenkins Pipeline</i></p>
              '''

              emailBody = emailBody
                .replace('%TENANT%', tenant.toString())
                .replace('%TOTAL%', totalSpend.toString())
                .replace('%USAGE%', usage.toString())
                .replace('%TABLE%', serviceTable)

              emailext(
                to: env.EMAIL_RECIPIENTS,
                subject: "📊 SMS Cost Report - ${env.TENANT_SHORT} | Client: ${env.CLIENT_NAME} | Environment: ${env.ENV_NAME}",
                mimeType: 'text/html',
                body: emailBody
              )

            } catch (err) {
              echo "❌ Failed for ${customer} - ${envName}: ${err}"
            }
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
