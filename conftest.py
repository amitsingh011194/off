import boto3
from datetime import date

ce = boto3.client('ce')

LIMIT = 1000  # your SMS quota
THRESHOLD = 70  # percent

def lambda_handler(event, context):
    start = date.today().replace(day=1).strftime('%Y-%m-%d')
    end = date.today().strftime('%Y-%m-%d')

    response = ce.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['AWS End User Messaging SMS']
            }
        }
    )

    amount = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
    percent = (amount / LIMIT) * 100

    print(f"Current Spend: ${amount}")
    print(f"Usage: {percent:.2f}%")

    if percent >= THRESHOLD:
        print("Threshold exceeded!")

        # Optional SNS alert
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='YOUR_SNS_TOPIC_ARN',
            Subject='SMS Cost Alert',
            Message=f'SMS spend reached {percent:.2f}% (${amount})'
        )

    return {
        "statusCode": 200,
        "body": f"Spend: ${amount}, Usage: {percent:.2f}%"
    }
