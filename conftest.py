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
    cron('30 5 * * 1')
  }

  environment {
    OIDC_ROLE_NAME   = "paymentor-oidc-role"
    EMAIL_RECIPIENTS = "amit.singh8@exlservice.com,Prashant.Varma@exlservice.com"
  }

  stages {

    stage('Initialize Context') {
      steps {
        script {

          fmt = { val -> String.format('%.2f', ((val ?: 0) as Double)) }

          tenantResults = [:]

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
          ALL_CUSTOMERS = ['tdb','lcc','nrg','demo','bcs','sce','nrgr','clientdemo']

          executionList = []

          if (params.CRON_MODE) {
            for (e in ENV_LIST) {
              for (c in ALL_CUSTOMERS) {
                executionList.add([env: e, customer: c])
              }
            }
          } else {
            if (params.RUN_ALL) {
              for (c in ALL_CUSTOMERS) {
                executionList.add([env: params.ENVIRONMENT, customer: c])
              }
            } else {
              executionList = [[env: params.ENVIRONMENT, customer: params.CUSTOMER]]
            }
          }
        }
      }
    }

    stage('Process Tenants') {
      steps {
        script {

          def branches = [:]

          for (t in executionList) {

            def CUSTOMER = t.customer
            def ENV_NAME = t.env

            branches["${ENV_NAME}-${CUSTOMER}"] = {

              def result = [
                env      : ENV_NAME,
                total    : 0,
                tenant   : CUSTOMER.toUpperCase(), // ✅ tenant name only
                customer : CUSTOMER,
                services : []
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

                result['total'] = BODY.total_spend ?: 0

                if (fileExists(logs)) {
                  def lines = readFile(logs).split('\\n')
                  for (l in lines) {
                    if (l.contains('→ $')) {
                      def p = l.split('→')
                      def svc = p[0].trim()
                      def val = (p[1].replace('$','').trim()) as Double
                      result['services'].add([name: svc, cost: val])
                    }
                  }
                }

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

          for (envName in ['prod','uat','dev']) {

            def envData = []

            for (entry in tenantResults) {
              def v = entry.value
              if (v['env'] == envName) {
                envData.add(v)
              }
            }

            if (envData.size() == 0) continue

            // safe sort
            for (int i = 0; i < envData.size(); i++) {
              for (int j = i + 1; j < envData.size(); j++) {
                if ((envData[j]['total'] ?: 0) > (envData[i]['total'] ?: 0)) {
                  def temp = envData[i]
                  envData[i] = envData[j]
                  envData[j] = temp
                }
              }
            }

            def GRAND_TOTAL = 0
            for (d in envData) {
              GRAND_TOTAL += (d['total'] ?: 0)
            }

            def FINAL_REPORT = ""

            for (d in envData) {

              def usagePercent = 0
              if (GRAND_TOTAL > 0) {
                usagePercent = (d['total'] * 100.0) / GRAND_TOTAL
              }

              def max1 = -1
              def max2 = -1
              def totalServiceCost = 0

              for (s in d['services']) {
                def cost = s['cost'] ?: 0
                totalServiceCost += cost

                if (cost > max1) {
                  max2 = max1
                  max1 = cost
                } else if (cost > max2) {
                  max2 = cost
                }
              }

              def serviceTable = ""

              for (s in d['services']) {

                def cost = s['cost'] ?: 0
                def color = ""

                if (cost == max1) color = "#f8d7da"
                else if (cost == max2) color = "#fff3cd"

                serviceTable += """
<tr style="background:${color};">
  <td>${s['name']}</td>
  <td><b>\$${fmt(cost)}</b></td>
</tr>
"""
              }

              // ✅ Total row added
              serviceTable += """
<tr style="background:#e2e3e5;font-weight:bold;">
  <td>Total</td>
  <td>\$${fmt(totalServiceCost)}</td>
</tr>
"""

              FINAL_REPORT += """
<div style="border:1px solid #e0e0e0;border-radius:10px;padding:15px;margin-bottom:15px;background:#fafafa;">

  <h3>🏢 Tenant: ${d['tenant']}</h3>
  <p><b>Client:</b> ${d['customer'].toUpperCase()}</p>

  <p><b>Total Spend:</b>
    <span style="color:#d9534f;font-weight:bold;">
      \$${fmt(d['total'])}
    </span>
  </p>

  <div style="background:#e9ecef;border-radius:5px;height:12px;">
    <div style="width:${fmt(usagePercent)}%;background:#28a745;height:12px;"></div>
  </div>

  <p style="font-size:12px;">Usage: <b>${fmt(usagePercent)}%</b></p>

  <table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;">
    <tr style="background:#f1f1f1;">
      <th>Service</th>
      <th>Cost</th>
    </tr>
    ${serviceTable}
  </table>

</div>
"""
            }

            def dateRange = "Weekly Summary"

            emailext(
              to: EMAIL_RECIPIENTS,
              subject: "PCAAS US | ${envName.toUpperCase()} | AWS Account ${envAccountMap[envName]} | Weekly Cost Summary | ${dateRange}",
              mimeType: 'text/html',
              body: """
<div style="font-family:Arial;background:#f4f6f8;padding:20px;">
  <div style="max-width:900px;margin:auto;background:#fff;padding:25px;border-radius:10px;">

    <h2>PCAAS US | ${envName.toUpperCase()} | AWS Account ${envAccountMap[envName]}</h2>

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
