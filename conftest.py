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

    /* ================================================= */
    stage('Initialize Context') {
    /* ================================================= */
      steps {
        script {
          GRAND_TOTAL   = 0
          FINAL_REPORT  = ""
          tenantResults = [:]

          envAccountMap = [
            dev  : '607436280417',
            uat  : '658960620175',
            prod : '016795361898'
          ]

          envAccountMapLFS = [
            dev  : '116981803571',
            uat  : '216989139664',
            prod : '767828744639'
          ]

          envAccountMapHSBC = [
            dev  : '088082905288',
            uat  : '793586321398',
            prod : '501957928506'
          ]

          TARGETS = [
            [env:'prod', customer:'tdb'],
            [env:'prod', customer:'lcc'],
            [env:'prod', customer:'fdr'],
            [env:'prod', customer:'nrg'],
            [env:'prod', customer:'demo'],
            [env:'prod', customer:'bcs'],
            [env:'prod', customer:'hsbcinm'],
            [env:'prod', customer:'hsbcmyh'],
            [env:'prod', customer:'sce'],
            [env:'prod', customer:'nrgr'],
            [env:'prod', customer:'lfs'],
            [env:'prod', customer:'clientdemo']
          ]

          executionList = params.RUN_ALL ?
            TARGETS :
            [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]
        }
      }
    }

    /* ================================================= */
    stage('Process Tenants (Parallel)') {
    /* ================================================= */
      steps {
        script {

          def branches = [:]

          executionList.each { t ->

            def CUSTOMER = t.customer
            def ENV_NAME = t.env

            branches["Tenant | ${CUSTOMER}"] = {

              def tenantTotal  = 0
              def tenantReport = ""

              try {
                echo "Processing ${CUSTOMER} - ${ENV_NAME}"

                /* ---- Mapping ---- */
                def mapFile = "resources/customer-mapping/${CUSTOMER}.json"
                if (!fileExists(mapFile)) return

                def mapping = readJSON file: mapFile
                if (!mapping.containsKey(ENV_NAME)) return

                def TENANT_SHORT = mapping[ENV_NAME].tenant_id

                /* ---- Account selection ---- */
                def selectedMap =
                  (CUSTOMER == 'lfs') ? envAccountMapLFS :
                  (CUSTOMER in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                  envAccountMap

                def ACCOUNT_ID = selectedMap[ENV_NAME]
                def ROLE_ARN  = "arn:aws:iam::${ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
                def LAMBDA    = "sb-prod3-3878909f-service_limit_lambdas"

                def payload = "payload-${CUSTOMER}.json"
                def output  = "output-${CUSTOMER}.json"
                def meta    = "meta-${CUSTOMER}.json"
                def logs    = "logs-${CUSTOMER}.txt"

                withAWS(role: ROLE_ARN, useNode: true) {
                  sh """
                    set -e
                    printf '{"tenant_prefix":"%s"}' "${TENANT_SHORT}" > ${payload}

                    aws lambda invoke \
                      --function-name ${LAMBDA} \
                      --region ${AWS_REGION} \
                      --cli-binary-format raw-in-base64-out \
                      --payload file://${payload} \
                      --log-type Tail \
                      ${output} > ${meta}

                    LOG_RESULT=\$(jq -r '.LogResult' ${meta})
                    [ "\$LOG_RESULT" != "null" ] && echo "\$LOG_RESULT" | base64 --decode > ${logs}
                  """
                }

                if (!fileExists(output)) return

                def resp = readJSON file: output
                def BODY = (resp.body instanceof String) ? readJSON(text: resp.body) : resp.body

                tenantTotal = BODY.total_spend ?: 0
                def USAGE   = BODY.usage_percent ?: 0
                def TENANT  = BODY.tenant ?: TENANT_SHORT

                def serviceTable = ""

                if (fileExists(logs)) {
                  readFile(logs).split('\n').each { l ->
                    if (l.contains('→ $')) {
                      def p = l.split('→')
                      serviceTable += """
<tr>
  <td>${p[0].trim()}</td>
  <td><b>\$${p[1].replace('$','').trim()}</b></td>
</tr>
"""
                    }
                  }
                }

                tenantReport = """
<hr/>
<h3>Tenant: ${TENANT}</h3>
<p><b>Client:</b> ${CUSTOMER.toUpperCase()}</p>
<p><b>Environment:</b> ${ENV_NAME.toUpperCase()}</p>
<p><b>Total Spend:</b> \$${tenantTotal}</p>
<p><b>Usage:</b> ${USAGE}%</p>

<table border="1" cellpadding="6" cellspacing="0">
<tr><th>Service</th><th>Cost</th></tr>
${serviceTable}
</table>
"""
              }
              catch (err) {
                echo "Failed for ${CUSTOMER}: ${err}"
              }

              tenantResults[CUSTOMER] = [
                total : tenantTotal,
                html  : tenantReport
              ]
            }
          }

          parallel branches
        }
      }
    }

    /* ================================================= */
    stage('Aggregate & Send Email') {
    /* ================================================= */
      steps {
        script {
          tenantResults.each { _, r ->
            GRAND_TOTAL  += (r.total as BigDecimal ?: 0)
            FINAL_REPORT += r.html ?: ""
          }

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

<p style="font-size:12px;color:#999;">Generated automatically by Jenkins CI/CD Pipeline</p>
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
