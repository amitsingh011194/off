import os

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

def is_safe_s3_key(folder, file_name):
    for part in (folder, file_name):
        if '..' in part or part.startswith('/') or part.startswith('\\'):
            return False
    return True

def lambda_handler(event, context):
    bucket_name = os.environ.get('DIGI_COLLECTS_STATIC_BUCKET_NAME')
    folder = os.environ.get('DIGI_COLLECTS_STATIC_FOLDER')
    file_name = os.environ.get('DIGI_COLLECTS_STATIC_FILE_NAME')

    if not all([bucket_name, folder, file_name]):
        return {
            'statusCode': 500,
            'body': 'Configurations Not Available'
        }

    if not is_safe_s3_key(folder, file_name):
        return {
            'statusCode': 400,
            'body': 'Content Not Available'
        }

    if boto3 is None:
        return {
            'statusCode': 500,
            'body': 'Supporting Packages Not Available'
        }

    s3 = boto3.client('s3')
    s3_key = f"{folder}/{file_name}"

    try:
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        html_content = response['Body'].read().decode('utf-8')
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': html_content
        }
    except ClientError:
        return {
            'statusCode': 404,
            'body': "File not found."
        }
    except Exception:
        return {
            'statusCode': 500,
            'body': "Internal server error."
        }
