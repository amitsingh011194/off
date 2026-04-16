properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','nrgr','lfs','clientdemo']),
    choice(name: 'ENVIRONMENT', choices: ['prod','uat','dev']),
    string(name: 'AWS_REGION', defaultValue: 'us-east-1'),
    booleanParam(name: 'RUN_ALL', defaultValue: true, description: 'Run for all customers (cron mode)')
  ])
])

pipeline {
  agent { label 'cicd' }

  triggers {
    cron('H H */7 * *')
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
            [env: 'prod', customer: 'nrgr'],
            [env: 'prod', customer: 'lfs'],
            [env: 'prod', customer: 'clientdemo']
          ]

          def executionList = params.RUN_ALL ? TARGETS :
            [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]

          for (t in executionList) {

            def customer = t.customer
            def envName  = t.env

            echo "Processing ${customer} - ${envName}"

            try {

              def mappingFile = "resources/customer-mapping/${customer}.json"
              if (!fileExists(mappingFile)) {
                echo "Mapping missing for ${customer}"
                continue
              }

              def mapping = readJSON file: mappingFile
              if (!mapping.containsKey(envName)) {
                echo "Env missing for ${customer}"
                continue
              }

              def tenantShort = mapping[envName].tenant_id

              def selectedMap =
                (customer == 'lfs') ? envAccountMapLFS :
                (customer in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                envAccountMap

              def accountId = selectedMap[envName]
              def roleArn = "arn:aws:iam::${accountId}:role/${OIDC_ROLE_NAME}"
              def lambdaName = "sb-prod3-3878909f-service_limit_lambdas"

              withAWS(role: roleArn, useNode: true) {

                sh """
                  set -e
                  printf '{"tenant_prefix":"%s"}' "${tenantShort}" > payload.json

                  aws lambda invoke \
                    --function-name ${lambdaName} \
                    --region ${AWS_REGION} \
                    --cli-binary-format raw-in-base64-out \
                    --payload file://payload.json \
                    --log-type Tail \
                    output.json > lambda_output.txt

                  LOG_RESULT=\$(cat lambda_output.txt | jq -r '.LogResult')

                  if [ "\$LOG_RESULT" != "null" ]; then
                    echo \$LOG_RESULT | base64 --decode > decoded_logs.txt
                  fi
                """
              }

              if (!fileExists('output.json')) {
                continue
              }

              def lambdaResponse = readJSON file: 'output.json'

              def body = (lambdaResponse.body instanceof String) ?
                          readJSON(text: lambdaResponse.body) :
                          lambdaResponse.body

              def tenant = body.tenant ?: tenantShort
              def totalSpend = body.total_spend ?: 0
              def usage = body.usage_percent ?: 0

              // GRAND TOTAL SAFE ADD (NO DOUBLE CONVERSION)
              GRAND_TOTAL += (totalSpend as BigDecimal ?: 0)

              def serviceTable = ""

              if (fileExists('decoded_logs.txt')) {

                def lines = readFile('decoded_logs.txt').split('\n')

                lines.each { line ->
                  if (line.contains('→ $')) {

                    def parts = line.split('→')
                    def service = parts[0].trim()
                    def costStr = parts[1].replace('$','').trim()

                    // SAFE: no parseDouble, just display
                    def costDisplay = costStr

                    serviceTable += """
<tr>
<td>${service}</td>
<td><b>\$${costDisplay}</b></td>
</tr>
"""
                  }
                }
              }

              FINAL_REPORT += """
<hr/>
<h3>Tenant: ${tenant}</h3>
<p><b>Client:</b> ${customer.toUpperCase()}</p>
<p><b>Environment:</b> ${envName.toUpperCase()}</p>
<p><b>Total Spend:</b> \$${totalSpend}</p>
<p><b>Usage:</b> ${usage}%</p>

<table border="1" cellpadding="6" cellspacing="0">
<tr><th>Service</th><th>Cost</th></tr>
${serviceTable}
</table>
"""

            } catch (err) {
              echo "Failed for ${customer}: ${err}"
            }
          }

          emailext(
            to: EMAIL_RECIPIENTS,
            subject: "📊 Consolidated Cost Report",
            mimeType: 'text/html',
            body: """
<h2>📊 Multi-Tenant Cost Monitoring</h2>

<p><b>Total Spend Across All Tenants:</b>
<span style="color:red;">\$${GRAND_TOTAL}</span></p>

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
