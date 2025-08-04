you gave me these suggestions. based on that, this is my final code:

import boto3
import psycopg2
import os
import json
from datetime import date
from botocore.exceptions import ClientError
 
def get_db_credentials():
    """Fetch DB credentials from AWS Secrets Manager"""
    secret_arn = "arn:aws:secretsmanager:us-east-1:658960620175:secret:/saas-platform/utp1/1674e330/lambdareadwrite-W8ITdi"  # Replace with actual ARN
    client = boto3.client('secretsmanager')
 
    try:
        response = client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        return secret['username'], secret['password']
    except ClientError as e:
        raise Exception(f"Unable to retrieve secret: {e}")
 
#def invoke_other_lambda(payload):
    """Invoke another Lambda and return response"""
    lambda_client = boto3.client('lambda')
    
    try:
        response = lambda_client.invoke(
            FunctionName='lambda-b-processing-handler',  # Replace with your actual Lambda function name
            InvocationType='RequestResponse',            # Wait for response (can also be 'Event' for async)
            Payload=json.dumps(payload)
        )
 
        response_payload = json.load(response['Payload'])
        return response_payload
 
    except Exception as e:
        raise Exception(f"Failed to invoke Lambda-B: {str(e)}")
 
def lambda_handler(event, context):
    try:
        # DB connection info
        DB_HOST = "sb-utp1-tenant-1674e330-health.cluster-cr81hny6qs45.us-east-1.rds.amazonaws.com"
        DB_PORT = 5432
        DB_NAME = "utp1db"
 
        # Get credentials
        DB_USER, DB_PASSWORD = get_db_credentials()
 
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
            connect_timeout=10  # Timeout in seconds)
        )
        cursor = conn.cursor()
 
        today = date.today().isoformat()
 
        # Query map
        queries = {
            "opsmonitor": f"SELECT * FROM paymentor.opsmonitor;",
            "etvalidations": f"SELECT * FROM paymentor.etvalidations WHERE createdatetime >= '{today}';",
            "ssplugin": f"SELECT * FROM paymentor.ssplugin WHERE createdatetime >= '{today}';",
            "debtshistory": f"SELECT * FROM paymentor.debtshistory WHERE createdatetime >= '{today}';",
            "paymentplanoptions": f"SELECT * FROM paymentor.paymentplanoptions;",
            "accountpaymentplan": f"SELECT * FROM paymentor.accountpaymentplan;",
            "accountpaymentplanhistory": "SELECT * FROM paymentor.accountpaymentplanhistory WHERE accountnumber = 11315;",
            "contactssnapshot": f"SELECT * FROM paymentor.pii.contactssnapshot WHERE createdatetime >= '{today}';",
            "debtsnapshot": f"SELECT originalcreditor, accountnumber FROM paymentor.debtsnapshot WHERE createdatetime >= '{today}';",
            "payments": f"SELECT * FROM  paymentor.payments where createdatetime >= current_date;",
            "communicationdecisions": f"""
                SELECT accountnumber, createdatetime, dslsmsengagement, event, seasonality, behaviorssegment,
                       exclusioncriteria, recommendedaction, smstemplate, countrycode, phonenumber1, batchid,
                       senderphonenumber, subjourney, dayssubjourney, originalcreditor, dateofsubjourney
                FROM paymentor.pii.communicationdecisions
                WHERE createdatetime >= '{today}'
                ORDER BY accountnumber;
            """,
            "decisionfeatures": f"SELECT * FROM paymentor.decisionfeatures WHERE createdatetime >= '{today}';",
            "communicationdecisions_dup": f"SELECT * FROM paymentor.pii.communicationdecisions WHERE createdatetime >= '{today}';",
            "communicationdecisionshistory": f"SELECT * FROM paymentor.communicationdecisionshistory WHERE createdatetime >= '{today}';",
            "chatshistory": "SELECT * FROM paymentor.chatshistory;",
            "communicationsent_by_accountnumber": f"SELECT * FROM paymentor.communicationssent WHERE date(createdatetime) = '{today}' ORDER BY accountnumber;",
            "communicationssent": f"SELECT * FROM paymentor.communicationssent WHERE date(createdatetime) = '{today}' ORDER BY createdatetime desc;",
            "smsevents": f"SELECT * FROM paymentor.smsevents ORDER by createdatetime desc;",
            "smsclicks": f"SELECT * FROM paymentor.smsclicks WHERE date(createdatetime) = '{today}' ORDER BY createdatetime desc;",
            "smslinks": f"SELECT * FROM paymentor.smslinks ORDER by createdatetime desc;"
        
        }

        # Create logs directory in /tmp
        logs_dir = "/tmp/logs"
        os.makedirs(logs_dir, exist_ok=True)
 
        saved_files = []
 
        for name, query in queries.items():
            cursor.execute(query)
            rows = cursor.fetchall()
            file_path = os.path.join(logs_dir, f"{name}.txt")
 
            with open(file_path, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(f"{row}\n")
 
            saved_files.append(file_path)
 
        cursor.close()
        conn.close()
 
        return {
            "statusCode": 200,
            "message": "Query results written to logs/",
            "files_created": saved_files
        }
 
    except Exception as e:
        return {
            "statusCode": 500,
            "error": str(e)
        }
 
