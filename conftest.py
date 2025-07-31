#!/bin/bash

# Ensure the script stops on the first error
set -e

# Assign parameters
TARGET_ENV=$1
CUSTOMER_NAME=$2
TENANT_ENV=$3
TENANT_ID=$4

# Define the output directory and file
OUTPUT_DIR="resources/customer-mapping"
OUTPUT_FILE="$OUTPUT_DIR/${CUSTOMER_NAME}.json"

JENKINSFILE="deploy/legacy/Jenkinsfile"

if [ ! -f  $OUTPUT_FILE ];then
  echo "--- First time customer onboard, creating file..."
  echo "{}" > $OUTPUT_FILE
  ls -l $OUTPUT_FILE
  cat $OUTPUT_FILE
fi

# Check env doesn't already exist
if jq -e --arg target_env "$TARGET_ENV" '.[$target_env] != null' "$OUTPUT_FILE" >/dev/null; then
    echo "❌ Error: Target environment '$TARGET_ENV' already exists in $OUTPUT_FILE."
    echo "🔧 Please manually update the file if needed."
    exit 1
fi

git config user.name "paymentor-automation"
git config user.email paymentor-automation@exlservice.com
git checkout main

# Add Json to file
echo "Adding $TARGET_ENV : { tenant_id: $TENANT_ID, tenant_env: $TENANT_ENV } to $CUSTOMER_NAME"

jq --arg target_env "$TARGET_ENV" --arg env "$TENANT_ENV" --arg id "$TENANT_ID" \
   '. + {($target_env): {"tenant_env": $env, "tenant_id": $id}}' "$OUTPUT_FILE" > temp.json && mv temp.json "$OUTPUT_FILE"

echo "✅ Successfully added $TARGET_ENV to $OUTPUT_FILE"

cat $OUTPUT_FILE

# Add new tenant to Jenkinsfile
if ! grep -q "$CUSTOMER_NAME" $JENKINSFILE; then
  echo "Adding customer to Deploy Jenkinsfile:"
  sed -i "s/'demo',/'demo','$CUSTOMER_NAME',/" $JENKINSFILE
  grep $CUSTOMER_NAME $JENKINSFILE
fi

# git commit back into repo
git add $OUTPUT_FILE $JENKINSFILE
git commit -m "Onboarded customer ${CUSTOMER_NAME} for ${TARGET_ENV}"

GITHUB_TOKEN=$(aws secretsmanager get-secret-value --secret-id /jenkins/github_repo_mgmt_api_token --query 'SecretString' --output text)
TOKENIZED_URL=$(echo $GIT_URL | sed "s.https://.https://$GITHUB_TOKEN@.")
git remote set-url origin $TOKENIZED_URL
git push $TOKENIZED_URL
