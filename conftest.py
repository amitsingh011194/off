import socket
import time
import json
import os
from datetime import datetime, timezone

ARTIFACT_DIR = "/tmp/network-cli-results"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def write_file(filename: str, content: str):
    path = os.path.join(ARTIFACT_DIR, filename)
    with open(path, "a") as f:
        f.write(content + "\n")

def dns_lookup(host: str):
    result = {
        "host": host,
        "canonical_name": None,
        "addresses": [],
        "error": None
    }

    try:
        cname, aliases, addresses = socket.gethostbyname_ex(host)
        result["canonical_name"] = cname
        result["addresses"] = addresses

    except Exception as e:
        result["error"] = str(e)

    return result


def tcp_connectivity_check(host: str, port: int, timeout_sec: int = 5):
    result = {
        "host": host,
        "port": port,
        "timeout_sec": timeout_sec,
        "success": False,
        "connect_time_ms": None,
        "error": None
    }

    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)

    try:
        sock.connect((host, port))
        end = time.time()
        result["success"] = True
        result["connect_time_ms"] = int((end - start) * 1000)

    except Exception as e:
        end = time.time()
        result["error"] = str(e)
        result["connect_time_ms"] = int((end - start) * 1000)

    finally:
        try:
            sock.close()
        except Exception:
            pass

    return result


def lambda_handler(event, context):
    """
    Expected event:
    {
      "target_host": "mfttisa.td.com",
      "target_port": 10022,
      "timeout_sec": 5
    }
    """

    target_host = event.get("target_host")
    target_port = int(event.get("target_port", 10022))
    timeout_sec = int(event.get("timeout_sec", 5))

    if not target_host:
        return {
            "status": "ERROR",
            "message": "target_host is required"
        }

    timestamp = datetime.now(timezone.utc).isoformat()

    header = [
        "========================================",
        "Network CLI Validation (Lambda)",
        f"Timestamp (UTC): {timestamp}",
        f"Host: {target_host}",
        f"Port: {target_port}",
        "========================================"
    ]

    # --- DNS lookup ---
    dns_result = dns_lookup(target_host)

    write_file("nslookup.out", "\n".join(header))
    write_file("nslookup.out", "DNS Lookup Result:")
    write_file("nslookup.out", json.dumps(dns_result, indent=2))

    # --- TCP connectivity ---
    conn_result = tcp_connectivity_check(
        target_host,
        target_port,
        timeout_sec=timeout_sec
    )

    write_file("connectivity.out", "\n".join(header))
    write_file("connectivity.out", "Port Connectivity Result:")
    write_file("connectivity.out", json.dumps(conn_result, indent=2))

    # --- Final response ---
    response = {
        "status": "SUCCESS" if conn_result["success"] else "FAILURE",
        "timestamp": timestamp,
        "dns": dns_result,
        "connectivity": conn_result,
        "lambda": {
            "function_name": context.function_name,
            "aws_request_id": context.aws_request_id
        }
    }

    return response


for this lambda, I need to test one more command:

telnet agenticai-lfs-dev-voiceassistant.wittyriver-10f7eba4.australiaeast.azurecontainerapps.io 443


can we please add this

agenticai-lfs-dev-voiceassistant.wittyriver-10f7eba4.australiaeast.azurecontainerapps.io 443

this can come from build with params

we already have a host and port parameter in jenkins pipeline:

properties([
    parameters([
        choice(name: 'CUSTOMER', choices: ['demo', 'lcc', 'fdr', 'nrg', 'nrgr', 'tdb', 'hsbcinm', 'hsbcmyh', 'sce', 'mf','pra', 'mbac', 'bcs', 'omf', 'lfs', 'clientdemo'], description: 'Which Customer do you want to deploy'),
        choice(name: 'ENVIRONMENT', choices: ['dev','uat','prod'], description: 'Which Environment you want to deploy to'),
        booleanParam(name: 'RUN_CLI_SCRIPT', defaultValue: false, description: 'Run CLI network validation'),
        string(name: 'TARGET_HOST', defaultValue: 'mfttisa.td.com', description: 'Target hostname for network validation'),
        string(name: 'TARGET_PORT', defaultValue: '10022', description: 'Target port for connectivity check')
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
                    git clone ${GIT_REPO_URL}
                    cd bu-dgt-paymentor-core-aws-app
                    git checkout client/${CUSTOMER}/${ENVIRONMENT}
                """
            }
        }

        stage('Network CLI Validation') {
            when {
                expression {
                    return params.RUN_CLI_SCRIPT &&
                           ['clientdemo','tdb','demo','lcc','nrg','nrgr','hsbcinm','hsbcmyh'].contains(params.CUSTOMER)
                }
            }
            steps {
                ansiColor('xterm') {
                    sh '''
                        set +e

                        ARTIFACT_DIR="network-cli-results"
                        mkdir -p $ARTIFACT_DIR

                        echo "========================================" | tee $ARTIFACT_DIR/nslookup.out
                        echo "DNS Lookup"                               | tee -a $ARTIFACT_DIR/nslookup.out
                        echo "Host: ${TARGET_HOST}"                    | tee -a $ARTIFACT_DIR/nslookup.out
                        echo "Timestamp: $(date -u)"                  | tee -a $ARTIFACT_DIR/nslookup.out
                        echo "========================================" | tee -a $ARTIFACT_DIR/nslookup.out
                        nslookup ${TARGET_HOST}                       | tee -a $ARTIFACT_DIR/nslookup.out

                        echo ""                                       | tee $ARTIFACT_DIR/connectivity.out
                        echo "========================================" | tee -a $ARTIFACT_DIR/connectivity.out
                        echo "Port Connectivity Check"                 | tee -a $ARTIFACT_DIR/connectivity.out
                        echo "Host: ${TARGET_HOST}"                    | tee -a $ARTIFACT_DIR/connectivity.out
                        echo "Port: ${TARGET_PORT}"                    | tee -a $ARTIFACT_DIR/connectivity.out
                        echo "Timestamp: $(date -u)"                  | tee -a $ARTIFACT_DIR/connectivity.out
                        echo "========================================" | tee -a $ARTIFACT_DIR/connectivity.out

                        timeout 5 bash -c "</dev/tcp/${TARGET_HOST}/${TARGET_PORT}"
                        RESULT=$?

                        if [ $RESULT -eq 0 ]; then
                            echo "SUCCESS: Connectivity successful"    | tee -a $ARTIFACT_DIR/connectivity.out
                        else
                            echo "FAILURE: Connectivity failed"        | tee -a $ARTIFACT_DIR/connectivity.out
                            # Uncomment below to FAIL pipeline
                            # exit 1
                        fi

                        echo "Network CLI validation completed"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'network-cli-results/**', fingerprint: true
                }
            }
        }

        // ---- Deployment stages go below ----
    }

    post {
        cleanup {
            deleteDir()
        }
    }
}


