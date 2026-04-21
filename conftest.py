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
  steps {
    script {

      /* ============================= */
      /* 1️⃣ Calculate Grand Total     */
      /* ============================= */
      GRAND_TOTAL = 0
      tenantResults.each { k, v ->
        if (v != null) {
          GRAND_TOTAL += (v.total ?: 0)
        }
      }

      /* ============================= */
      /* 2️⃣ Convert Map → List        */
      /* ============================= */
      def tenantList = []

      tenantResults.each { k, v ->
        if (v != null) {
          tenantList.add([
            customer: k,
            total   : (v.total ?: 0),
            html    : v.html ?: ""
          ])
        } else {
          echo "Skipping ${k} — no data"
        }
      }

      /* ============================= */
      /* 3️⃣ Sort by total DESC        */
      /* ============================= */
      tenantList.sort { -it.total }

      /* ============================= */
      /* 4️⃣ Build Final Report        */
      /* ============================= */
      FINAL_REPORT = ""

      tenantList.each { t ->

        def tenantTotal = t.total
        def customer    = t.customer

        def usagePercent = 0
        if (GRAND_TOTAL > 0) {
          usagePercent = (tenantTotal * 100.0) / GRAND_TOTAL
          usagePercent = Math.round(usagePercent * 100) / 100
        }

        def html = t.html

        // Extract service table
       def serviceTableMatch = (html =~ /(?s)<table.*?<\/table>/)
def serviceTable = serviceTableMatch ? serviceTableMatch[0] : ""

        // Extract tenant name
       def tenantMatch = (html =~ /<h3>Tenant: (.*?)<\/h3>/)
def tenantName = tenantMatch ? tenantMatch[0][1] : "N/A"

        /* ============================= */
        /* 🎨 Card UI                   */
        /* ============================= */
        FINAL_REPORT += """
<div style="border:1px solid #e0e0e0;border-radius:10px;padding:15px;margin-bottom:20px;background:#fafafa;">

  <h3>🏢 Tenant: ${tenantName}</h3>

  <p><b>Client:</b> ${customer.toUpperCase()}</p>
  <p><b>Total Spend:</b> <span style="color:#d9534f;font-weight:bold;">\$${tenantTotal}</span></p>

  <!-- Usage Bar -->
  <div style="background:#e9ecef;border-radius:5px;height:12px;">
    <div style="width:${usagePercent}%;background:#28a745;height:12px;"></div>
  </div>
  <p style="font-size:12px;">Usage: <b>${usagePercent}%</b></p>

  <div style="margin-top:10px;">
    ${serviceTable}
  </div>

</div>
"""
      }

      /* ============================= */
      /* 5️⃣ Send Email                */
      /* ============================= */
      emailext(
        to: EMAIL_RECIPIENTS,
        subject: "📊 Consolidated Cost Report",
        mimeType: 'text/html',
        body: """
<div style="font-family:Arial;background:#f4f6f8;padding:20px;">
  <div style="max-width:900px;margin:auto;background:#fff;padding:25px;border-radius:10px;">

    <h2>📊 Multi-Tenant Cost Monitoring</h2>

    <div style="background:#fff3cd;border:1px solid #ffeeba;padding:15px;border-radius:8px;margin:20px 0;">
      <div>💰 Grand Total Spend</div>
      <div style="font-size:30px;font-weight:bold;color:#a94442;">
        \$${GRAND_TOTAL}
      </div>
    </div>

    ${FINAL_REPORT}

    <p style="font-size:12px;color:#999;text-align:center;">
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


I need some help in this, first thing, it should contruct the lambda name based on the environment we are deploying it to.

for eg, sb-prod3-3878909f-service_limit_lambdas this is the lambda name currently, 

I need it to be:  sb-prod3-3878909f-service_limit_lambdas


I needs this prod3 and 3878909f this to be entered dynamically.

or let me tell you..

I guess its better we get rid of this whole selection thing as of now I guess:

 choice(name: 'CUSTOMER', choices: ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','nrgr','lfs','clientdemo']),


 because the single lambda is going to work for all of the above tenants as they are all in one single account itself.

for for prod, lambda name is:  sb-prod3-3878909f-service_limit_lambdas
dev sb-dev14-3878909f-service_limit_lambdas
uat sb-utp2-3878909f-service_limit_lambdas

 
