properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['bcs', 'lcc', 'fdr', 'nrg', 'demo', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'mf','pra', 'mbac', 'nrgr', 'omf', 'lfs', 'clientdemo'], description: 'Which Customer do you want to deploy'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Environment you want to deploy to'),
        booleanParam(name: 'RUN_NETWORK_COMMANDS', defaultValue: false, description: 'Run CLI network validation'),
        string(
  name: 'AWS_REGION',
  defaultValue: 'us-east-1',
  description: 'AWS region for SMS/Voice and Lambda operations'
),
        booleanParam(
  name: 'RUN_LAMBDA_TAG_SCAN',
  defaultValue: false,
  description: 'Scan all Lambdas and report missing required tags'
),




        // 🔹 NEW PARAMETERS FOR TAGGING
        booleanParam(name: 'RUN_PHONEPOOL_TAGGING', defaultValue: false, description: 'Replicate phone pool tags to all phone numbers'),


        
        string(name: 'PHONE_POOL_ID', defaultValue: '', description: 'Phone Pool ID (e.g. pool-c3974e14baab42999cb0c545ee4b3297)'),

        string(name: 'TARGET_HOST', defaultValue: 'mfttisa.td.com', description: 'Target hostname for network validation'),
        string(name: 'TARGET_PORT', defaultValue: '10022', description: 'Target port for connectivity check'),
        booleanParam(
  name: 'RUN_RDS_USER_SETUP',
  defaultValue: false,
  description: 'Create / ensure read-only RDS user on writer instance'
),


string(
  name: 'RDS_NEW_DB_USER',
  defaultValue: 'varonisreadonly',
  description: 'Read-only DB username to create/ensure'
),

password(
  name: 'RDS_NEW_DB_PASSWORD',
  defaultValue: '',
  description: 'Password for the read-only DB user'
),
 // 🔹 NEW PARAMETERS FOR SSH and PGP Work
booleanParam(
  name: 'RUN_KEY_GENERATION',
  defaultValue: false,
  description: 'Generate PGP and SSH keys'
),

password(
  name: 'KEY_PASSPHRASE',
  defaultValue: '',
  description: 'Passphrase for PGP and SSH private keys'
),

string(
  name: 'PGP_EMAIL',
  defaultValue: 'devops@exlservice.com',
  description: 'Email to associate with PGP key'
)


    ])
])


pipeline {
    agent {
        label 'cicd'
    }

    environment {
        CUSTOMER        = "${params.CUSTOMER}"
        ENVIRONMENT     = "${params.ENVIRONMENT}"
        TARGET_HOST     = "${params.TARGET_HOST}"
        TARGET_PORT     = "${params.TARGET_PORT}"
        GIT_REPO_URL    = "https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-dgt-paymentor-core-aws-app.git"
        OIDC_ROLE_NAME  = "paymentor-oidc-role"
    }

    stages {

        stage('Auth Check') {
            when {
                expression { "${ENVIRONMENT}" != "dev" }
            }
            steps {
                sh """
                    chmod +x scripts/env-protection.sh
                    ./scripts/env-protection.sh deploy
                """
            }
        }

        stage('Get customer mapping') {
            steps {
                script {
                    currentBuild.description = """CUSTOMER: ${CUSTOMER}
ENVIRONMENT: ${ENVIRONMENT}
BUILT BY: ${env.BUILD_USER_ID}"""

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
                    env.AWS_ROLE_ARN  = "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${OIDC_ROLE_NAME}"
                    


                    env.TENANT_ENV = sh(
                        script: "jq -r --arg env '${ENVIRONMENT}' '.[\$env].tenant_env' resources/customer-mapping/${CUSTOMER}.json",
                        returnStdout: true
                    ).trim()

                    env.TENANT_ID = sh(
                        script: "jq -r --arg env '${ENVIRONMENT}' '.[\$env].tenant_id' resources/customer-mapping/${CUSTOMER}.json",
                        returnStdout: true
                    ).trim()
                    env.RDS_DB_IDENTIFIER = "sb-${env.TENANT_ENV}-tenant-${env.TENANT_ID}-health-instance"
                    env.RDS_DB_NAME       = "${env.TENANT_ENV}db"
                   

                    echo "AWS_ACCOUNT_ID : ${AWS_ACCOUNT_ID}"
                    echo "AWS_ROLE_ARN  : ${AWS_ROLE_ARN}"
                    echo "TENANT_ID     : ${TENANT_ID}"
                    echo "TENANT_ENV    : ${TENANT_ENV}"
                }
            }
        }

      stage('Checkout App repo') {
  steps {
    sh """
      set -e

      REPO_DIR="bu-dgt-paymentor-core-aws-app"

      if [ -d "\$REPO_DIR/.git" ]; then
        echo "Repo already exists. Reusing and updating it..."
        cd "\$REPO_DIR"
        git fetch --all
        git reset --hard
        git checkout client/${CUSTOMER}/${ENVIRONMENT}
        git pull origin client/${CUSTOMER}/${ENVIRONMENT}
      else
        echo "Fresh clone of repo..."
        git clone ${GIT_REPO_URL}
        cd "\$REPO_DIR"
        git checkout client/${CUSTOMER}/${ENVIRONMENT}
      fi
    """
  }
}


stage('Scan Lambda Tag Compliance') {
  when {
    expression {
      return params.RUN_LAMBDA_TAG_SCAN
    }
  }

  steps {
    ansiColor('xterm') {
      withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
        withEnv([
          "AWS_REGION=${params.AWS_REGION ?: (env.AWS_DEFAULT_REGION ?: 'us-east-1')}",
          "ARTIFACT_DIR=lambda-tag-scan"
        ]) {

          sh '''
set -e

echo "=================================================="
echo "Lambda Tag Compliance Scan"
echo "Region: $AWS_REGION"
echo "=================================================="

mkdir -p "$ARTIFACT_DIR"

REQUIRED_JSON='[
  "Application",
  "CostCode",
  "sb:cost:environment",
  "sb:cost:tenant",
  "sb:rg:tenant"
]'

echo "Fetching Lambda resources via Resource Groups Tagging API..."

NEXT_TOKEN=""
> "$ARTIFACT_DIR/all-lambdas.json"

while :; do
  if [ -z "$NEXT_TOKEN" ]; then
    RESP=$(aws resourcegroupstaggingapi get-resources \
      --region "$AWS_REGION" \
      --resource-type-filters lambda:function \
      --output json)
  else
    RESP=$(aws resourcegroupstaggingapi get-resources \
      --region "$AWS_REGION" \
      --resource-type-filters lambda:function \
      --pagination-token "$NEXT_TOKEN" \
      --output json)
  fi

  echo "$RESP" | jq '.ResourceTagMappingList[]' >> "$ARTIFACT_DIR/all-lambdas.json"
  NEXT_TOKEN=$(echo "$RESP" | jq -r '.PaginationToken // empty')
  [ -z "$NEXT_TOKEN" ] && break
done

TOTAL=$(wc -l < "$ARTIFACT_DIR/all-lambdas.json" | tr -d ' ')
echo "Total Lambdas discovered: $TOTAL"

jq -s --argjson required "$REQUIRED_JSON" '
  map({
    Arn: .ResourceARN,
    TagKeys: (.Tags // [] | map(.Key)),
    Missing: ($required - (.Tags // [] | map(.Key)))
  })
  | map(select((.TagKeys | length == 0) or (.Missing | length > 0)))
' "$ARTIFACT_DIR/all-lambdas.json" \
> "$ARTIFACT_DIR/noncompliant.json"

jq -r '
  .[] |
  [
    .Arn,
    (if (.TagKeys|length)==0 then "NO_TAGS"
     else "MISSING:" + (.Missing|join("|")) end)
  ] | @csv
' "$ARTIFACT_DIR/noncompliant.json" \
> "$ARTIFACT_DIR/noncompliant.csv"

echo "Reports generated in $ARTIFACT_DIR/"
'''
        }
      }
    }
  }


}

stage('Create RDS Read-Only User') {
  when {
    expression {
      return params.RUN_RDS_USER_SETUP &&
             params.RDS_NEW_DB_USER?.trim() &&
             params.RDS_NEW_DB_PASSWORD?.toString()?.trim()
    }
  }

  steps {
    ansiColor('xterm') {
      withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {

        withEnv([
          "AWS_REGION=${params.AWS_REGION ?: (env.AWS_DEFAULT_REGION ?: 'us-east-1')}",
          "LAMBDA_NAME=sb-${TENANT_ENV}-${TENANT_ID}-rds_lambda",
          "ARTIFACT_DIR=rds-user-setup"
        ]) {

          sh '''
set -e
mkdir -p "$ARTIFACT_DIR"

echo "=================================================="
echo "Invoking Lambda to create RDS read-only user"
echo "Lambda      : $LAMBDA_NAME"
echo "Region      : $AWS_REGION"
echo "DB User     : ${RDS_NEW_DB_USER}"
echo "=================================================="

PAYLOAD=$(cat <<EOF
{
  "NEW_DB_USER": "$RDS_NEW_DB_USER",
  "NEW_DB_PASSWORD": "$RDS_NEW_DB_PASSWORD",
  "DB_IDENTIFIER": "$RDS_DB_IDENTIFIER",
  "DB_NAME": "$RDS_DB_NAME"
}
EOF
)

aws lambda invoke \
  --region "$AWS_REGION" \
  --function-name "sb-${TENANT_ENV}-${TENANT_ID}-rds_lambda" \
  --cli-binary-format raw-in-base64-out \
  --payload "$PAYLOAD" \
  rds-user-setup/lambda-response.json

echo "--------------------------------------------------"
echo "Lambda response:"
cat "$ARTIFACT_DIR/lambda-response.json"
echo
echo "--------------------------------------------------"

# Optional: basic success check
if grep -q '"status": "error"' "$ARTIFACT_DIR/lambda-response.json"; then
  echo "ERROR: Lambda reported failure"
  exit 1
fi

echo "=================================================="
echo "RDS read-only user ensured via Lambda successfully"
echo "=================================================="
'''
        }
      }
    }
  }
}





stage('Network CLI Validation (via VPC Lambda)') {
  when {
    expression {
      return params.RUN_NETWORK_COMMANDS &&
             ['clientdemo','tdb','demo','lcc','nrg','nrgr','hsbcinm','fdr','hsbcmyh','lfs']
                 .contains(params.CUSTOMER)
    }
  }

  steps {
    ansiColor('xterm') {
      withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {
        withEnv([
          "ARTIFACT_DIR=network-cli-results"
        ]) {

          sh '''
set -e

mkdir -p "$ARTIFACT_DIR"

LAMBDA_NAME="sb-${TENANT_ENV}-${TENANT_ID}-network_lambda"

PAYLOAD_FILE="$ARTIFACT_DIR/payload.json"
RESPONSE_FILE="$ARTIFACT_DIR/lambda-response.json"
PRETTY_FILE="$ARTIFACT_DIR/lambda-response.pretty.json"
INVOKE_META="$ARTIFACT_DIR/invoke-meta.json"
HUMAN_FILE="$ARTIFACT_DIR/network-summary.txt"

echo "Building Lambda payload..."
cat > "$PAYLOAD_FILE" <<EOF
{
  "target_host": "${TARGET_HOST}",
  "target_port": ${TARGET_PORT}
}
EOF

echo "Invoking Lambda: $LAMBDA_NAME"
aws lambda invoke \
  --function-name "$LAMBDA_NAME" \
  --payload fileb://"$PAYLOAD_FILE" \
  "$RESPONSE_FILE" \
  --log-type Tail \
  > "$INVOKE_META"

jq . "$RESPONSE_FILE" > "$PRETTY_FILE" || cp "$RESPONSE_FILE" "$PRETTY_FILE"

jq -r '
"========================================
Network CLI Validation (via VPC Lambda)
========================================
Timestamp        : \\(.timestamp)

DNS Check
---------
Host             : \\(.dns.host)
Canonical Name   : \\(.dns.canonical_name)
Resolved IPs     : \\(.dns.addresses | join(\", \"))
DNS Error        : \\(.dns.error // \"None\")

Port Connectivity
-----------------
Host             : \\(.connectivity.host)
Port             : \\(.connectivity.port)
Timeout (sec)    : \\(.connectivity.timeout_sec)
Success          : \\(.connectivity.success)
Connect Time(ms) : \\(.connectivity.connect_time_ms)
Error            : \\(.connectivity.error // \"None\")

Execution Context
-----------------
Lambda Function  : \\(.lambda.function_name)
AWS Request ID   : \\(.lambda.aws_request_id)

Overall Status   : \\(.status)
========================================
"
' "$RESPONSE_FILE" > "$HUMAN_FILE"

echo "Artifacts written to $ARTIFACT_DIR/"
'''
        }
      }
    }
  }


}

stage('Generate PGP & SSH Keys') {
  when {
    expression {
      return params.RUN_KEY_GENERATION &&
             params.KEY_PASSPHRASE?.toString()?.trim()
    }
  }

  steps {
    ansiColor('xterm') {
      sh '''
set -e

echo "=============================================="
echo "Key Generation Stage"
echo "Customer   : ${CUSTOMER}"
echo "Environment: ${ENVIRONMENT}"
echo "=============================================="

KEY_DIR="key-artifacts/${CUSTOMER}/${ENVIRONMENT}"
mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

############################################
# 1. Generate PGP Key (Non-interactive)
############################################

PGP_NAME="paymentor-${CUSTOMER}-pgp"
PGP_EMAIL="${PGP_EMAIL}"

cat > pgp-batch.conf <<EOF
%echo Generating PGP key
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: ${PGP_NAME}
Name-Email: ${PGP_EMAIL}
Expire-Date: 0
Passphrase: ${KEY_PASSPHRASE}
%commit
%echo done
EOF

gpg --batch --gen-key pgp-batch.conf

# Export public key (no passphrase needed)
gpg --armor --export "${PGP_NAME}" \
  > "${KEY_DIR}/${PGP_NAME}.pub.gpg"

# Export private key (requires loopback pinentry)
export GPG_TTY=$(tty || true)

gpg --batch --yes \
  --pinentry-mode loopback \
  --passphrase "${KEY_PASSPHRASE}" \
  --armor --export-secret-keys "${PGP_NAME}" \
  > "${KEY_DIR}/${PGP_NAME}.private.gpg"

############################################
# 2. Generate SSH Key (Non-interactive)
############################################
SSH_KEY_NAME="paymentor-${CUSTOMER}-ssh"

ssh-keygen \
  -t rsa \
  -b 4096 \
  -N "${KEY_PASSPHRASE}" \
  -f "${KEY_DIR}/${SSH_KEY_NAME}" \
  -q

############################################
# 3. Secure permissions
############################################

chmod 600 "${KEY_DIR}"/*

echo "=============================================="
echo "Keys generated successfully:"
ls -l "${KEY_DIR}"
sleep 240
echo "=============================================="
'''
    }
  }
}


stage('Replicate Phone Pool Tags to Phone Numbers') {
  when {
    expression {
      return params.RUN_PHONEPOOL_TAGGING && params.PHONE_POOL_ID?.trim()
    }
  }
  steps {
    ansiColor('xterm') {
      withAWS(role: "${AWS_ROLE_ARN}", useNode: true) {

        // Pass parameters to the shell as environment variables (safe & portable)
        withEnv([
          "POOL_ID=${params.PHONE_POOL_ID ?: 'pool-c3974e14baab42999cb0c545ee4b3297'}",
          "AWS_REGION=${params.AWS_REGION ?: (env.AWS_DEFAULT_REGION ?: 'us-east-1')}"
        ]) {

          sh '''
set -e

echo "Processing Pool: $POOL_ID (region: $AWS_REGION)"

# --- 1) Resolve the Pool ARN (needed to read the pool's tags) ---
POOL_ARN=$(aws pinpoint-sms-voice-v2 describe-pools \
  --region "$AWS_REGION" \
  --pool-ids "$POOL_ID" \
  --query "Pools[0].PoolArn" \
  --output text)

if [ -z "$POOL_ARN" ] || [ "$POOL_ARN" = "None" ]; then
  echo "Could not resolve PoolArn for pool id: $POOL_ID"
  exit 1
fi

echo "Resolved PoolArn: $POOL_ARN"

# --- 2) Fetch the pool's tags (JSON array of {Key,Value}) ---
# list-tags-for-resource (v2) returns a 'Tags' array: [{Key,Value}, ...]
POOL_TAGS_JSON=$(aws pinpoint-sms-voice-v2 list-tags-for-resource \
  --region "$AWS_REGION" \
  --resource-arn "$POOL_ARN" \
  --query "Tags" \
  --output json)

# If there are no tags, make sure we pass an empty JSON array to tag-resource
if [ -z "$POOL_TAGS_JSON" ] || [ "$POOL_TAGS_JSON" = "null" ]; then
  POOL_TAGS_JSON="[]"
fi

# Optional: show how many tags we found (requires jq)
if command -v jq >/dev/null 2>&1; then
  echo "Pool has $(echo "$POOL_TAGS_JSON" | jq 'length') tag(s)."
else
  echo "Pool tags fetched. (Install 'jq' to print count.)"
fi

# --- 3) List all origination identities (phone numbers / sender IDs) in the pool ---
# Use the correct field 'OriginationIdentityArn'
RESOURCE_ARNS=$(aws pinpoint-sms-voice-v2 list-pool-origination-identities \
  --region "$AWS_REGION" \
  --pool-id "$POOL_ID" \
  --query "OriginationIdentities[].OriginationIdentityArn" \
  --output text)

if [ -z "$RESOURCE_ARNS" ]; then
  echo "No origination identities found in pool $POOL_ID."
  exit 0
fi

# --- 4) Apply the pool's tags to each identity ---
# tag-resource overwrites values for existing keys and adds new keys.
for ARN in $RESOURCE_ARNS; do
  echo "--------------------------------------------------"
  echo "Tagging Resource: $ARN"
  aws pinpoint-sms-voice-v2 tag-resource \
    --region "$AWS_REGION" \
    --resource-arn "$ARN" \
    --tags "$POOL_TAGS_JSON"
  echo "Successfully tagged."
done

echo "=================================================="
echo "All identities in pool $POOL_ID have been updated to match pool tags."
'''
        }
      }
    }
  }
}



        // ---- Deployment stages go below ----
    }

post {
  always {
    echo "Pipeline execution completed. Preparing artifacts ZIP by stage..."

    script {
      sh '''
set +e

mkdir -p artifacts

ARTIFACT_DIRS=""

if [ -d "lambda-tag-scan" ]; then
  mkdir -p stage-lambda-tag-scan
  mv lambda-tag-scan/* stage-lambda-tag-scan/ 2>/dev/null || true
  ARTIFACT_DIRS="$ARTIFACT_DIRS stage-lambda-tag-scan"
fi

if [ -d "network-cli-results" ]; then
  mkdir -p stage-network-cli
  mv network-cli-results/* stage-network-cli/ 2>/dev/null || true
  ARTIFACT_DIRS="$ARTIFACT_DIRS stage-network-cli"
fi

if [ -d "phonepool-tagging" ]; then
  mkdir -p stage-phonepool-tagging
  mv phonepool-tagging/* stage-phonepool-tagging/ 2>/dev/null || true
  ARTIFACT_DIRS="$ARTIFACT_DIRS stage-phonepool-tagging"
fi

if [ -n "$ARTIFACT_DIRS" ]; then
  echo "Zipping artifacts: $ARTIFACT_DIRS"
  zip -r artifacts/pipeline-artifacts.zip $ARTIFACT_DIRS
else
  echo "No artifacts generated. Skipping zip step."
  touch artifacts/pipeline-artifacts.zip
fi
'''
    }

    archiveArtifacts artifacts: 'artifacts/pipeline-artifacts.zip', fingerprint: true
    deleteDir()
  }
}




}
