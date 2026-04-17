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

    /* ============================= */
    stage('Initialize Context') {
    /* ============================= */
      steps {
        script {
          FINAL_REPORT = ""
          GRAND_TOTAL  = 0

          envAccountMap = [
            dev:  '607436280417',
            uat:  '658960620175',
            prod: '016795361898'
          ]

          envAccountMapLFS = [
            dev:  '116981803571',
            uat:  '216989139664',
            prod: '767828744639'
          ]

          envAccountMapHSBC = [
            dev:  '088082905288',
            uat:  '793586321398',
            prod: '501957928506'
          ]

          TARGETS = [
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

          executionList = params.RUN_ALL ?
            TARGETS :
            [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]
        }
      }
    }

    /* ============================= */
    stage('Process Tenants') {
    /* ============================= */
      steps {
        script {

          for (t in executionList) {

            def CUSTOMER = t.customer
            def ENV_NAME = t.env

            stage("Tenant | ${CUSTOMER}") {

              try {
                echo "Processing ${CUSTOMER} - ${ENV_NAME}"

                /* ------- Resolve Mapping ------- */
                def mappingFile = "resources/customer-mapping/${CUSTOMER}.json"
                if (!fileExists(mappingFile)) {
                  echo "Mapping missing for ${CUSTOMER}"
                  return
                }

                def mapping = readJSON file: mappingFile
                if (!mapping.containsKey(ENV_NAME)) {
                  echo "Env missing for ${CUSTOMER}"
                  return
                }

                def TENANT_SHORT = mapping[ENV_NAME].tenant_id

                /* ------- Account Resolution ------- */
                def selectedMap =
                  (CUSTOMER == 'lfs') ? envAccountMapLFS :
                  (CUSTOMER in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                  envAccountMap

                def ACCOUNT_ID = selectedMap[ENV_NAME]
                def ROLE_ARN  = "arn:aws:iam::${ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
                def LAMBDA    = "sb-prod3-3878909f-service_limit_lambdas"

                /* ------- Invoke Lambda ------- */
                withAWS(role: ROLE_ARN, useNode: true) {
                  sh """
                    set -e
                    printf '{"tenant_prefix":"%s"}' "${TENANT_SHORT}" > payload.json

                    aws lambda invoke \
                      --function-name ${LAMBDA} \
                      --region ${AWS_REGION} \
                      --cli-binary-format raw-in-base64-out \
                      --payload file://payload.json \
                      --log-type Tail \
                      output.json > lambda_output.txt

                    LOG_RESULT=\$(jq -r '.LogResult' lambda_output.txt)
                    if [ "\$LOG_RESULT" != "null" ]; then
                      echo "\$LOG_RESULT" | base64 --decode > decoded_logs.txt
                    fi
                  """
                }

                if (!fileExists('output.json')) {
                  return
                }

                /* ------- Parse Response ------- */
                def lambdaResponse = readJSON file: 'output.json'

                def BODY = (lambdaResponse.body instanceof String)
                  ? readJSON(text: lambdaResponse.body)
                  : lambdaResponse.body

                def TENANT = BODY.tenant ?: TENANT_SHORT
                def TOTAL  = BODY.total_spend ?: 0
                def USAGE  = BODY.usage_percent ?: 0

                GRAND_TOTAL += (TOTAL as BigDecimal ?: 0)

                /* ------- Build Service Table ------- */
                def SERVICE_TABLE = ""

                if (fileExists('decoded_logs.txt')) {
                  readFile('decoded_logs.txt').split('\n').each { line ->
                    if (line.contains('→ $')) {
                      def parts = line.split('→')
                      SERVICE_TABLE += """
<tr>
  <td>${parts[0].trim()}</td>
  <td><b>\$${parts[1].replace('$','').trim()}</b></td>
</tr>
"""
                    }
                  }
                }

                /* ------- Append Report ------- */
                FINAL_REPORT += """
<hr/>
<h3>Tenant: ${TENANT}</h3>
<p><b>Client:</b> ${CUSTOMER.toUpperCase()}</p>
<p><b>Environment:</b> ${ENV_NAME.toUpperCase()}</p>
<p><b>Total Spend:</b> \$${TOTAL}</p>
<p><b>Usage:</b> ${USAGE}%</p>

<table border="1" cellpadding="6" cellspacing="0">
  <tr><th>Service</th><th>Cost</th></tr>
  ${SERVICE_TABLE}
</table>
"""

              } catch (err) {
                echo "Failed for ${CUSTOMER}: ${err}"
              }
            }
          }
        }
      }
    }

    /* ============================= */
    stage('Send Email Report') {
    /* ============================= */
      steps {
        script {
          emailext(
            to: EMAIL_RECIPIENTS,
            subject: "📊 Consolidated Cost Report",
            mimeType: 'text/html',
            body: """
<div style="font-family:Arial;background:#f4f6f8;padding:20px;">
 <div style="max-width:900px;margin:auto;background:#fff;padding:20px;border-radius:8px;">
  <h2>📊 Multi‑Tenant Cost Monitoring Report</h2>

  <table width="100%" style="background:#fff3cd;border:1px solid #ffeeba;margin:20px 0;">
   <tr><td>
    <span>💰 Grand Total Spend</span><br/>
    <span style="font-size:28px;font-weight:bold;color:#a94442;">
      \$${GRAND_TOTAL}
    </span>
   </td></tr>
  </table>

  ${FINAL_REPORT}

  <p style="font-size:12px;color:#999;">
    Generated automatically by Jenkins CI/CD Pipeline
  </p>
 </div>
</div>
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
