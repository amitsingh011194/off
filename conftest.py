This below jenkins file is working perfectly as of now,
I need some more help with enhancement, I need that for each tenant, it highlight the service costing the highest with maybe red colour and the the second highest cost service in yellow colour. please rewrite the whole jenkins file with this change.


properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['tdb','lcc','nrg','demo','bcs','sce','nrgr','clientdemo']),
    choice(name: 'ENVIRONMENT', choices: ['prod','uat','dev']),
    string(name: 'AWS_REGION', defaultValue: 'us-east-1'),
    booleanParam(name: 'RUN_ALL', defaultValue: true),
    booleanParam(name: 'CRON_MODE', defaultValue: true)
  ])
])

pipeline {
  agent { label 'cicd' }

  triggers {
    cron('30 15 * * *')
  }

  environment {
    OIDC_ROLE_NAME   = "paymentor-oidc-role"
    EMAIL_RECIPIENTS = "amit.singh8@exlservice.com,Suman.Porel@exlservice.com,Prashant.Varma@exlservice.com"
  }

  stages {

    stage('Initialize Context') {
      steps {
        script {

          // ✅ Safe formatter
          fmt = { val ->
            return String.format('%.2f', ((val ?: 0) as Double))
          }

          tenantResults = [:]

          // ✅ Single account map only (simplified)
          envAccountMap = [
            dev  : '607436280417',
            uat  : '658960620175',
            prod : '016795361898'
          ]

          envCodeMap = [
            prod: 'prod3',
            dev : 'dev14',
            uat : 'utp2'
          ]

          ENV_LIST = ['prod','uat','dev']

          // ✅ Cleaned customer list
          ALL_CUSTOMERS = ['tdb','lcc','nrg','demo','bcs','sce','nrgr','clientdemo']

          executionList = []

          if (params.CRON_MODE) {
            ENV_LIST.each { e ->
              ALL_CUSTOMERS.each { c ->
                executionList.add([env: e, customer: c])
              }
            }
          } else {
            executionList = params.RUN_ALL ?
              ALL_CUSTOMERS.collect { c -> [env: params.ENVIRONMENT, customer: c] } :
              [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]
          }
        }
      }
    }

    stage('Process Tenants') {
      steps {
        script {

          def branches = [:]

          executionList.each { t ->

            def CUSTOMER = t.customer
            def ENV_NAME = t.env

            branches["${ENV_NAME}-${CUSTOMER}"] = {

              def result = [
                env         : ENV_NAME,
                total       : 0,
                tenant      : "",
                customer    : CUSTOMER,
                serviceTable: ""
              ]

              try {

                def mapFile = "resources/customer-mapping/${CUSTOMER}.json"
                if (!fileExists(mapFile)) {
                  tenantResults["${ENV_NAME}-${CUSTOMER}"] = result
                  return
                }

                def mapping = readJSON file: mapFile
                if (!mapping.containsKey(ENV_NAME)) {
                  tenantResults["${ENV_NAME}-${CUSTOMER}"] = result
                  return
                }

                def TENANT_SHORT = mapping[ENV_NAME].tenant_id

                // ✅ Only one account logic now
                def ACCOUNT_ID = envAccountMap[ENV_NAME]
                def ROLE_ARN   = "arn:aws:iam::${ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"

                def ENV_CODE = envCodeMap[ENV_NAME]
                def LAMBDA = "sb-${ENV_CODE}-3878909f-service_limit_lambdas"

                def payload = "payload-${ENV_NAME}-${CUSTOMER}.json"
                def output  = "output-${ENV_NAME}-${CUSTOMER}.json"
                def meta    = "meta-${ENV_NAME}-${CUSTOMER}.json"
                def logs    = "logs-${ENV_NAME}-${CUSTOMER}.txt"

                withAWS(role: ROLE_ARN, useNode: true) {
                  sh """
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

                if (!fileExists(output)) {
                  tenantResults["${ENV_NAME}-${CUSTOMER}"] = result
                  return
                }

                def resp = readJSON file: output
                def BODY = (resp.body instanceof String) ? readJSON(text: resp.body) : resp.body

                def tenantTotal = BODY.total_spend ?: 0
                def TENANT      = BODY.tenant ?: TENANT_SHORT

                def serviceTable = ""

                if (fileExists(logs)) {
                  readFile(logs).split('\\n').each { l ->
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

                result.total = tenantTotal
                result.tenant = TENANT
                result.serviceTable = serviceTable

              } catch (err) {
                echo "Error ${CUSTOMER}-${ENV_NAME}: ${err}"
              }

              tenantResults["${ENV_NAME}-${CUSTOMER}"] = result
            }
          }

          parallel branches
        }
      }
    }

    stage('Send Emails Per Environment') {
      steps {
        script {

          ['prod','uat','dev'].each { envName ->

            def envData = []

            tenantResults.each { k, v ->
              if (v.env == envName) {
                envData.add(v)
              }
            }

            if (envData.size() == 0) return

            envData.sort { -it.total }

            def GRAND_TOTAL = 0
            envData.each { d -> GRAND_TOTAL += d.total }

            def FINAL_REPORT = ""

            envData.each { d ->

              def usagePercent = 0
              if (GRAND_TOTAL > 0) {
                usagePercent = (d.total * 100.0) / GRAND_TOTAL
                usagePercent = Math.round(usagePercent * 100) / 100
              }

              FINAL_REPORT += """
<div style="border:1px solid #e0e0e0;border-radius:10px;padding:15px;margin-bottom:15px;background:#fafafa;">

  <h3>🏢 Tenant: ${d.tenant}</h3>
  <p><b>Client:</b> ${d.customer.toUpperCase()}</p>

  <p><b>Total Spend:</b>
    <span style="color:#d9534f;font-weight:bold;">
      \$${fmt(d.total)}
    </span>
  </p>

  <div style="background:#e9ecef;border-radius:5px;height:12px;">
    <div style="width:${usagePercent}%;background:#28a745;height:12px;"></div>
  </div>

  <p style="font-size:12px;">Usage: <b>${fmt(usagePercent)}%</b></p>

  <div style="margin-top:10px;">
    <table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;">
      <tr style="background:#f1f1f1;">
        <th>Service</th>
        <th>Cost</th>
      </tr>
      ${d.serviceTable}
    </table>
  </div>

</div>
"""
            }

            emailext(
              to: EMAIL_RECIPIENTS,
              subject: "📊 PCAAS Account Cost Report - ${envAccountMap[envName]} - ${envName.toUpperCase()}",
              mimeType: 'text/html',
              body: """
<div style="font-family:Arial;background:#f4f6f8;padding:20px;">
  <div style="max-width:900px;margin:auto;background:#fff;padding:25px;border-radius:10px;">

    <h2>📊 PCAAS Account Cost Report - ${envAccountMap[envName]} - ${envName.toUpperCase()}</h2>

    <div style="background:#fff3cd;border:1px solid #ffeeba;padding:15px;border-radius:8px;margin:20px 0;">
      <div>💰 Grand Total Spend</div>
      <div style="font-size:30px;font-weight:bold;color:#a94442;">
        \$${fmt(GRAND_TOTAL)}
      </div>
    </div>

    ${FINAL_REPORT}

  </div>
</div>
"""
            )
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
