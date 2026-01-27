import boto3
import json
import logging
import os
import random
import shutil
import string
import subprocess

from aws_xray_sdk.core import patch_all
from botocore.exceptions import ClientError

patch_all()


logger = logging.getLogger()
logger.setLevel(os.environ.get('log_level', 'INFO'))

region_name = os.environ['region_name']
migrations_s3_bucket = os.environ['migrations_s3_bucket']
migrations_s3_prefix = os.environ['migrations_s3_prefix']
placeholder_secrets_dict = json.loads(os.environ["placeholder_secrets"])
kms_key_id = os.environ['kms_key_id']
rds_creds_secret_name = os.environ['secret_name']
aws_account_id = os.environ['aws_account_id']

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
secrets_manager = boto3.client('secretsmanager', region_name=region_name)

try:
    response = lambda_client.list_tags(
        Resource=f"arn:aws:lambda:{region_name}:{aws_account_id}:function:{os.environ['AWS_LAMBDA_FUNCTION_NAME']}"
    )
    tags = response.get('Tags', {})
    secrets_manager_tags = [{'Key': k, 'Value': v} for k, v in tags.items()]
except Exception:
    logger.error(f"Failed to fetch tags for the function")
    raise

secret_dict = json.loads(secrets_manager.get_secret_value(SecretId=rds_creds_secret_name)['SecretString'])

host = secret_dict['host']
database = secret_dict['database']
password = secret_dict['password']
port = secret_dict['port']
user = secret_dict['username']
cypher_key = secret_dict['cypher_key']

pw_characters = string.ascii_letters + string.digits


def lambda_handler(event, context):
    # Flyway executable in lambda layer
    flyway_exe = "/opt/bin/flyway"
    flyway_url = f"jdbc:postgresql://{host}:{port}/{database}"
    migrations_folder = "/tmp/migrations"

    try:
        command = event.get('command')
        baseline_version = event.get('baselineVersion')

        if command:
            logger.info("Running lambda event Flyway command")
            event_command_list = command.split()
            command_list = [flyway_exe, f"-url={flyway_url}", f"-user={user}", f"-password={password}"]
            command_list.extend(event_command_list)
            command_result = subprocess.run(command_list, capture_output=True, text=True, check=True)
            logger.info(f"lambda event Flyway command output: {command_result.stdout}")

            return {
                'statusCode': 200,
                'body': command_result.stdout
            }

        if baseline_version:
            logger.info(f"Setting baseline version to {baseline_version}")
            baseline_command_list = [flyway_exe, "-defaultSchema=flyway", f"-url={flyway_url}", f"-user={user}", f"-password={password}", f"-baselineVersion={baseline_version}", "baseline"]
            logger.info("Running Flyway baseline command")
            baseline_result = subprocess.run(baseline_command_list, capture_output=True, text=True, check=True)
            logger.info(f"Flyway baseline output: {baseline_result.stdout}")


        placeholder_password_list = get_placeholder_password_list(placeholder_secrets_dict)

        # Run Flyway migrate
        download_migrations(migrations_s3_bucket, migrations_s3_prefix, migrations_folder)
        logger.info("Running Flyway migrate command")
        migrate_command_list = [flyway_exe, f"-locations=filesystem:{migrations_folder}", "-defaultSchema=flyway", f"-url={flyway_url}", f"-user={user}", f"-password={password}"]
        migrate_command_list.extend(placeholder_password_list)
        migrate_command_list.append("migrate")
        migrate_result = subprocess.run(migrate_command_list, capture_output=True, text=True, check=True)
        logger.info(f"Flyway migrate output: {migrate_result.stdout}")

        return {
            'statusCode': 200,
            'body': migrate_result.stdout
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess error while running Flyway command: {e.stderr}")
        return {
            'statusCode': 500,
            'body': e.stderr
        }
    except Exception as e:
        logger.exception("Error during attempt to run Flyway command")
        return {
            'statusCode': 500,
            'body': str(e)
        }
    finally:
        if os.path.exists(migrations_folder):
            shutil.rmtree(migrations_folder)


def generate_password():
    password_length = 8
    return ''.join(random.choices(pw_characters, k=password_length))


def download_migrations(s3_bucket: str, s3_prefix:str, local_path:str) -> None:
    try:
        logger.info(f"Creating {local_path} folder to store migrations")
        os.makedirs(local_path, exist_ok=True)
        logger.info("Downloading migrations from s3")
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
        files = [content['Key'] for content in response.get('Contents', []) if content['Key'].endswith('.sql')]

        for file_key in files:
            file_name = file_key.split('/')[-1]
            s3_client.download_file(s3_bucket, file_key,
                             os.path.join(local_path, file_name))

        logger.info(f"Downloaded {files} from s3 to {local_path}")
    except Exception:
        logger.exception("Failed to download migrations from s3")
        raise

def get_placeholder_password_list(placeholder_secrets_dict):
    placeholder_password_list = []
    for placeholder, secret_name in placeholder_secrets_dict.items():
        try:
            db_user_secret = json.loads(secrets_manager.get_secret_value(SecretId=secret_name)['SecretString'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"Secret {secret_name} not found. Creating secret")
                user_password = generate_password()
                username = secret_name.rsplit('/', 1)[-1]
                secret_string = {
                    "dbname": database,
                    "host": host,
                    "key": cypher_key,
                    "password": user_password,
                    "port": port,
                    "username": username
                }
                secrets_manager.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(secret_string),
                    KmsKeyId=kms_key_id,
                    Tags=secrets_manager_tags
                )
            else:
                raise
        else:
            logger.info(f"Secret {secret_name} already exists")
            user_password = db_user_secret['password']

        placeholder_password_list.append(f"-placeholders.{placeholder}={user_password}")

    return placeholder_password_list
