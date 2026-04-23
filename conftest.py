there is only 1 issue now, 

💰 Grand Total Spend
$1264.37
🏢 Tenant: 69fc3147

Client: CLIENTDEMO

Total Spend: $371.7

Usage: 37.17%

Service	Cost
AWS End User Messaging	$44.19
AWS Key Management Service	$1.46
AWS Lambda	$0.04
AWS Secrets Manager	$1.15
Amazon API Gateway	$0.0
Amazon CloudFront	$0.96
Amazon DynamoDB	$0.0
Amazon Elastic Container Service	$12.52
Amazon Elastic Load Balancing	$37.33
Amazon Kinesis Firehose	$0.0
Amazon Lex	$0.37
Amazon Relational Database Service	$243.38
Amazon Route 53	$4.02
Amazon SageMaker	$23.88
Amazon Simple Email Service	$0.04
Amazon Simple Notification Service	$0.01
Amazon Simple Queue Service	$2.11
Amazon Simple Storage Service	$0.1
AmazonCloudWatch	$0.15


if you see the percentage, 

Usage: 37.17%


its just assuming the account limit to be 1000 dollars and based on that, its finding out the usage percentage.

but what we need is, it should be calculated this way:   37.17/1264.17*100


here's the current jenkins file, please rewrite it with the fix:

properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','nrgr','lfs','clientdemo']),
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

          envCodeMap = [
            prod: 'prod3',
            dev : 'dev14',
            uat : 'utp2'
          ]

          ENV_LIST = ['prod','uat','dev']
          ALL_CUSTOMERS = ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','nrgr','lfs','clientdemo']

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

              def result = [env: ENV_NAME, total: 0, html: ""]

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

                def selectedMap =
                  (CUSTOMER == 'lfs') ? envAccountMapLFS :
                  (CUSTOMER in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                  envAccountMap

                def ACCOUNT_ID = selectedMap[ENV_NAME]
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
                def USAGE       = BODY.usage_percent ?: 0
                def TENANT      = BODY.tenant ?: TENANT_SHORT

                /* -------- SERVICE TABLE -------- */
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

                result.html = """
<div style="border:1px solid #e0e0e0;border-radius:10px;padding:15px;margin-bottom:15px;background:#fafafa;">

  <h3>🏢 Tenant: ${TENANT}</h3>
  <p><b>Client:</b> ${CUSTOMER.toUpperCase()}</p>

  <p><b>Total Spend:</b>
    <span style="color:#d9534f;font-weight:bold;">\$${tenantTotal}</span>
  </p>

  <div style="background:#e9ecef;border-radius:5px;height:12px;">
    <div style="width:${USAGE}%;background:#28a745;height:12px;"></div>
  </div>
  <p style="font-size:12px;">Usage: <b>${USAGE}%</b></p>

  <div style="margin-top:10px;">
    <table border="1" cellpadding="6" cellspacing="0" style="width:100%;border-collapse:collapse;">
      <tr style="background:#f1f1f1;">
        <th>Service</th>
        <th>Cost</th>
      </tr>
      ${serviceTable}
    </table>
  </div>

</div>
"""
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
            envData.each { d -> FINAL_REPORT += d.html }

            emailext(
              to: EMAIL_RECIPIENTS,
              subject: "📊 Cost Report - ${envName.toUpperCase()}",
              mimeType: 'text/html',
              body: """
<div style="font-family:Arial;background:#f4f6f8;padding:20px;">
  <div style="max-width:900px;margin:auto;background:#fff;padding:25px;border-radius:10px;">

    <h2>📊 Cost Report - ${envName.toUpperCase()}</h2>

    <div style="background:#fff3cd;border:1px solid #ffeeba;padding:15px;border-radius:8px;margin:20px 0;">
      <div>💰 Grand Total Spend</div>
      <div style="font-size:30px;font-weight:bold;color:#a94442;">
        \$${String.format('%.2f', GRAND_TOTAL)}
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
