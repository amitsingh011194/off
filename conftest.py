import boto3
import os
from datetime import date

ce = boto3.client('ce')
sns = boto3.client('sns')

# ✅ Read from environment variables
LIMIT = float(os.environ.get("LIMIT", 1000))  # default fallback
THRESHOLD = float(os.environ.get("THRESHOLD", 70))  # default fallback
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")


def lambda_handler(event, context):
    try:
        start = date.today().replace(day=1).strftime('%Y-%m-%d')
        end = date.today().strftime('%Y-%m-%d')

        print(f"Fetching cost from {start} to {end}")

     response = ce.get_cost_and_usage(
    TimePeriod={'Start': start, 'End': end},
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
    ]
)

        amount = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        percent = (amount / LIMIT) * 100

        print(f"Current Spend: ${amount}")
        print(f"Usage: {percent:.2f}% of ${LIMIT}")

        # 🚨 Threshold check
        if percent >= THRESHOLD:
            print("Threshold exceeded!")

            if SNS_TOPIC_ARN:
                message = (
                    f"🚨 SMS Cost Alert 🚨\n\n"
                    f"Current Spend: ${amount:.2f}\n"
                    f"Usage: {percent:.2f}%\n"
                    f"Threshold: {THRESHOLD}%\n"
                )

                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject="SMS Cost Alert",
                    Message=message
                )

                print("SNS notification sent")
            else:
                print("SNS_TOPIC_ARN not configured!")

        return {
            "statusCode": 200,
            "body": {
                "spend": amount,
                "usage_percent": round(percent, 2)
            }
        }

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise
