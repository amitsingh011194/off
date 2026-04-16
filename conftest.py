properties([
  parameters([
    choice(name: 'CUSTOMER', choices: ['tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','mf','pra','mbac','nrgr','omf','lfs','clientdemo']),
    choice(name: 'ENVIRONMENT', choices: ['prod','uat','dev']),
    string(name: 'AWS_REGION', defaultValue: 'us-east-1')
  ])
])
 
pipeline {
  agent { label 'cicd' }
 
  environment {
    OIDC_ROLE_NAME   = "paymentor-oidc-role"
    EMAIL_RECIPIENTS = "amit.singh8@exlservice.com"
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

stage('Resolve Tenant Mapping') {
  steps {
    script {
 
      def customer = params.CUSTOMER?.toLowerCase()
      def envName  = params.ENVIRONMENT?.toLowerCase()
 
      def mappingFile = "resources/customer-mapping/${customer}.json"
 
      if (!fileExists(mappingFile)) {
        error "❌ Mapping file not found: ${mappingFile}"
      }
 
      def mapping = readJSON file: mappingFile
 
      if (!mapping.containsKey(envName)) {
        error "❌ Environment '${envName}' not found in ${mappingFile}"
      }
 
      def tenantShort = mapping[envName].tenant_id
      def tenantEnv   = mapping[envName].tenant_env
 
      // Store globally
      env.CLIENT_NAME  = customer.toUpperCase()
      env.ENV_NAME     = envName.toUpperCase()
      env.TENANT_SHORT = tenantShort
      env.TENANT_ENV   = tenantEnv
 
      echo """
      ✅ Mapping Resolved:
      Client       : ${env.CLIENT_NAME}
      Environment  : ${env.ENV_NAME}
      Tenant Short : ${env.TENANT_SHORT}
      Tenant Env   : ${env.TENANT_ENV}
      """
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
  echo "Tenant Prefix: ${TENANT_SHORT}"

  # ✅ Clean JSON creation (no encoding issues)
  printf '{"tenant_prefix":"%s"}' "${TENANT_SHORT}" > payload.json

  echo "Payload:"
  cat payload.json

  aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --region $AWS_REGION \
  --cli-binary-format raw-in-base64-out \
  --payload file://payload.json \
  --log-type Tail \
  output.json > lambda_output.txt

  echo "Lambda invocation completed"

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
    }
  }
}
 

 
 
stage('Send Cost Alert Email') {
  steps {
    script {
 
      if (!fileExists('output.json')) {
        error "Lambda output.json not found"
      }
 
      def lambdaResponse = readJSON file: 'output.json'
 
      def body = [:]
      if (lambdaResponse.body instanceof String) {
        body = readJSON text: lambdaResponse.body
      } else if (lambdaResponse.body instanceof Map) {
        body = lambdaResponse.body
      }
 
      def tenant = body.tenant_prefix ?: 'N/A'
      def totalSpend = body.total_spend ?: 0
      def usage      = body.usage_percent ?: 0
 
      // 🔥 NEW: Parse logs
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



Now since this is working perfectly, Its time we move on to the next stage in this.

I want to run it as a cron job in every 30 mins for now just for testing but eventually later on we will run it weekly.

then I also want to run it for all of these tenants at the same time or through a loop:

tdb','lcc','fdr','nrg','demo','bcs','hsbcinm','hsbcmyh','sce','nrgr','lfs','clientdemo'


let me give you a reference of how i want it to run, just hold on.




properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['tdb','lcc'], description: 'Customer'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Environment'),
        booleanParam(name: 'RUN_ALL', defaultValue: true, description: 'Run for all customers/environments (used by cron)')
    ])
])

pipeline {
    agent { label 'cicd' }

    triggers {
        cron('H */6 * * *')  // every 6 hours
    }

    environment {
        OIDC_ROLE_NAME = "paymentor-oidc-role"
        AWS_REGION     = "us-east-1"
    }

    stages {

        stage('Stop RDS') {
            steps {
                script {

                    // ✅ ADD THIS BLOCK HERE
            echo "===== TIME INFO ====="
            sh '''
            echo "UTC Time : $(date -u)"
            echo "IST Time : $(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST')"
            '''
            echo "====================="

                    // 🔹 Account mapping
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

                    // 🔹 Customer → RDS mapping
                  def RDS_MAP = [
    dev: [
        tdb: "sb-dev14-tenant-3878909f-health-instance",
        lcc: "sb-dev14-tenant-00d1f964-health-instance"
    ],
    uat: [
        tdb: "sb-utp2-tenant-3878909f-health-instance",
        lcc: "sb-utp2-tenant-00d1f964-health-instance"
    ],
    prod: [
        tdb: "sb-prod3-tenant-3878909f-health-instance",
        lcc: "sb-prod3-tenant-00d1f964-health-instance"
    ]
]

                    // 🔹 Define targets for cron (ALL combos)
                    def TARGETS = [
                        [env: 'dev',  customer: 'tdb'],
                        [env: 'dev',  customer: 'lcc'],
                        [env: 'uat',  customer: 'tdb'],
                        [env: 'uat',  customer: 'lcc'],
                        [env: 'prod', customer: 'tdb'],
                        [env: 'prod', customer: 'lcc']
                    ]

                 

                    def executionList = []

if (params.RUN_ALL) {
    echo "Running in FULL mode (cron)"
    executionList = TARGETS
} else {
    echo "Running in SINGLE mode (manual)"
    executionList.add([env: params.ENVIRONMENT, customer: params.CUSTOMER])
}

                    // 🔁 Main loop
                    for (t in executionList) {

                        def envKey = t.env
                        def customerKey = t.customer

                        echo "=================================="
                        echo "Processing ${customerKey} - ${envKey}"
                        echo "=================================="

                        if (!RDS_MAP.containsKey(envKey) || !RDS_MAP[envKey].containsKey(customerKey)) {
                            echo "No mapping found, skipping..."
                            continue
                        }

                        def selectedMap =
                            (customerKey == 'lfs') ? envAccountMapLFS :
                            (customerKey in ['hsbcinm','hsbcmyh']) ? envAccountMapHSBC :
                            envAccountMap

                        def accountId = selectedMap[envKey]
                        def roleArn = "arn:aws:iam::${accountId}:role/${OIDC_ROLE_NAME}"

                        def db = RDS_MAP[envKey][customerKey]

                     withAWS(role: roleArn, useNode: true, region: AWS_REGION) {

    echo "Checking DB: ${db}"

    // 🔹 Get engine type
    def engine = sh(
        script: """
        aws rds describe-db-instances \
          --db-instance-identifier ${db} \
          --query 'DBInstances[0].Engine' \
          --output text 2>/dev/null || echo "NOT_FOUND"
        """,
        returnStdout: true
    ).trim()

    if (engine == "NOT_FOUND") {
        echo "DB ${db} not found, skipping..."
        return
    }

    echo "Engine: ${engine}"

    // 🔹 Get status
    def status = sh(
        script: """
        aws rds describe-db-instances \
          --db-instance-identifier ${db} \
          --query 'DBInstances[0].DBInstanceStatus' \
          --output text
        """,
        returnStdout: true
    ).trim()

    echo "Status: ${status}"

    // 🔹 Debug sleep (as requested)
    echo "Sleeping for 5 seconds..."
    sleep(time: 5, unit: 'SECONDS')

    if (status == "available") {

       if (engine.contains("aurora")) {

    echo "Aurora detected. Fetching cluster..."

    def clusterId = sh(
        script: """
        aws rds describe-db-instances \
          --db-instance-identifier ${db} \
          --query 'DBInstances[0].DBClusterIdentifier' \
          --output text
        """,
        returnStdout: true
    ).trim()

    echo "Stopping cluster: ${clusterId}"

    sh "aws rds stop-db-cluster --db-cluster-identifier ${clusterId}"

    // ✅ ADD HERE 👇
    echo "Waiting for cluster to transition..."
    sleep(time: 20, unit: 'SECONDS')

    echo "Checking cluster status..."
    sh """
    aws rds describe-db-clusters \
      --db-cluster-identifier ${clusterId} \
      --query 'DBClusters[0].Status'
    """
}
else {

            echo "Stopping standard RDS instance..."
            sh "aws rds stop-db-instance --db-instance-identifier ${db}"
        }

    } else {
        echo "Skipping ${db} (${status})"
    }
}
                    }
                }
            }
        }
    }

    post {
  always {
    echo "RDS automation completed."

    echo "===== NEXT RUN INFO ====="

    sh '''
# Current UTC time
CURRENT_UTC=$(date -u +"%Y-%m-%d %H:%M:%S")

# Next run UTC (+6 hours)
NEXT_UTC=$(date -u -d "+6 hours" +"%Y-%m-%d %H:%M:%S")

# Convert to IST
CURRENT_IST=$(TZ=Asia/Kolkata date +"%Y-%m-%d %H:%M:%S IST")
NEXT_IST=$(TZ=Asia/Kolkata date -d "+6 hours" +"%Y-%m-%d %H:%M:%S IST")

echo "-----------------------------------"
echo "Current Execution Time (IST): $CURRENT_IST"
echo "Next Automatic Trigger (IST): $NEXT_IST"
echo "-----------------------------------"
'''
  }
}
}




