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
    cron('H H */7 * *')   // your schedule (fix later if needed)
  }

  environment {
    OIDC_ROLE_NAME   = "paymentor-oidc-role"
    EMAIL_RECIPIENTS = "amit.singh8@exlservice.com"
  }

  stages {

    stage('Process Tenants') {
      steps {
        script {

          def FINAL_REPORT = ""
          def GRAND_TOTAL = 0

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

          def executionList = params.RUN_ALL ? TARGETS : [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]

          for (t in executionList) {

            def customer = t.customer
            def envName  = t.env

            echo "=================================="
            echo "Processing ${customer} - ${envName}"
            echo "=================================="

            try {

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

              def selectedMap =
                (customer == 'lfs') ? envAccountMapLFS :
                (customer in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                envAccountMap

              env.AWS_ACCOUNT_ID = selectedMap[envName]
              env.AWS_ROLE_ARN   = "arn:aws:iam::${env.AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
              env.LAMBDA_NAME    = "sb-prod3-3878909f-service_limit_lambdas"

              withAWS(role: "${env.AWS_ROLE_ARN}", useNode: true) {
                sh '''
                  set -e

                  echo "Invoking Lambda: ${LAMBDA_NAME}"
                  printf '{"tenant_prefix":"%s"}' "${TENANT_SHORT}" > payload.json

                  aws lambda invoke \
                    --function-name $LAMBDA_NAME \
                    --region $AWS_REGION \
                    --cli-binary-format raw-in-base64-out \
                    --payload file://payload.json \
                    --log-type Tail \
                    output.json > lambda_output.txt

                  LOG_RESULT=$(cat lambda_output.txt | jq -r '.LogResult')

                  if [ "$LOG_RESULT" != "null" ]; then
                    echo $LOG_RESULT | base64 --decode > decoded_logs.txt
                  fi
                '''
              }

              if (!fileExists('output.json')) {
                continue
              }

              def lambdaResponse = readJSON file: 'output.json'

              def body = [:]
              if (lambdaResponse.body instanceof String) {
                body = readJSON text: lambdaResponse.body
              } else {
                body = lambdaResponse.body
              }

              def tenant = body.tenant ?: env.TENANT_SHORT
              def totalSpend = (body.total_spend ?: 0).toDouble()
              def usage      = body.usage_percent ?: 0

              GRAND_TOTAL += totalSpend

              def serviceTable = ""

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

              FINAL_REPORT += """
<hr/>
<h3>Tenant: ${tenant}</h3>
<p><b>Client:</b> ${env.CLIENT_NAME}</p>
<p><b>Environment:</b> ${env.ENV_NAME}</p>
<p><b>Total Spend:</b> <span style="color:red;">$${totalSpend}</span></p>
<p><b>Usage:</b> ${usage}%</p>

<table border="1" cellpadding="6" cellspacing="0">
<tr><th>Service</th><th>Cost</th></tr>
${serviceTable}
</table>
"""

            } catch (err) {
              echo "❌ Failed for ${customer}: ${err}"
            }
          }

          // =========================
          // SINGLE CONSOLIDATED EMAIL
          // =========================

          emailext(
            to: env.EMAIL_RECIPIENTS,
            subject: "📊 Consolidated Cost Report | ${new Date()}",
            mimeType: 'text/html',
            body: """
<h2>📊 Multi-Tenant Cost Monitoring</h2>

<p><b>Total Spend Across All Tenants:</b> 
<span style="color:red;">$${String.format('%.2f', GRAND_TOTAL)}</span></p>

${FINAL_REPORT}

<br/><p><i>Generated from Jenkins Pipeline</i></p>
"""
          )
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
