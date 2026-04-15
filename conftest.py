Breadcrumbsbu-digital-paymentor-core-app/devops_handled_lambdas/service_limit_lambdas
/lambda_function.py
Go to file
t
Latest commit
amit253714
amit253714
Update lambda_function.py
05c1147
 · 
2 days ago
History
Breadcrumbsbu-digital-paymentor-core-app/devops_handled_lambdas/service_limit_lambdas
/lambda_function.py
File metadata and controls

Code

Blame
135 lines (112 loc) · 4.05 KB
import boto3
import os
from datetime import date

ce = boto3.client('ce')
sns = boto3.client('sns')

LIMIT = float(os.environ.get("LIMIT", 1000))
THRESHOLD = float(os.environ.get("THRESHOLD", 70))
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

TAG_KEY = "sb:cost:tenant"
TENANT_ID = os.environ.get("TENANT_ID")


def lambda_handler(event, context):
    try:
        if not TENANT_ID:
            raise ValueError("TENANT_ID is not set")

        start = date.today().replace(day=1).strftime('%Y-%m-%d')
        end = date.today().strftime('%Y-%m-%d')

        print(f"Fetching cost for tenant: {TENANT_ID}")

        # -----------------------------
        # 1️⃣ TOTAL COST (Overview)
        # -----------------------------
        total_response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            Filter={
                "And": [
                    {
                        "Dimensions": {
                            "Key": "SERVICE",
                            "Values": ["AWS End User Messaging"]
                        }
                    },
                    {
                        "Tags": {
                            "Key": TAG_KEY,
                            "Values": [TENANT_ID]
                        }
                    }
                ]
            }
        )

        total_amount = float(
            total_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
        )

        percent = (total_amount / LIMIT) * 100 if LIMIT > 0 else 0

        # -----------------------------
        # 2️⃣ SERVICE-WISE BREAKDOWN
        # -----------------------------
        service_response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"}
            ],
            Filter={
                "Tags": {
                    "Key": TAG_KEY,
                    "Values": [TENANT_ID]
                }
            }
        )

        service_costs = {}

        for group in service_response['ResultsByTime'][0]['Groups']:
            service_name = group['Keys'][0]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])

            if cost > 0:
                service_costs[service_name] = round(cost, 2)

        # -----------------------------
        # 📊 Print Summary
        # -----------------------------
        print(f"\n=== TENANT SUMMARY ===")
        print(f"Tenant: {TENANT_ID}")
        print(f"Total Spend: ${round(total_amount, 2)}")
        print(f"Usage: {percent:.2f}% of ${LIMIT}")

        print("\n=== SERVICE BREAKDOWN ===")
        for svc, cost in service_costs.items():
            print(f"{svc} → ${cost}")

        # -----------------------------
        # 🚨 ALERT
        # -----------------------------
        if percent >= THRESHOLD:
            print("Threshold exceeded!")

            if SNS_TOPIC_ARN:
                breakdown_text = "\n".join(
                    [f"{k}: ${v}" for k, v in service_costs.items()]
                )

                message = (
                    f"🚨 SMS Cost Alert 🚨\n\n"
                    f"Tenant: {TENANT_ID}\n"
                    f"Total Spend: ${round(total_amount, 2)}\n"
                    f"Usage: {percent:.2f}%\n\n"
                    f"Service Breakdown:\n{breakdown_text}"
                )

                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject=f"{TENANT_ID} Cost Alert",
                    Message=message
                )

                print("SNS notification sent")

        return {
            "statusCode": 200,
            "body": {
                "tenant": TENANT_ID,
                "total_spend": round(total_amount, 2),
                "usage_percent": round(percent, 2),
                "service_breakdown": service_costs
            }
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        raise



we had created this lambda,  for tdb prod account but I think this one lambda can be used for all the tenants in the prod account because all of them are there in one account itself and catagorized by the tenant ID.
we can just alter the payload that we provide to lambda dynamically.

  I guess currently the lambda function is pretty generic already but ther main thing we are providibg the lambda is the tenant ID from the env variables:

 "TENANT_ID": "3878909f-e2f8-4588-b8fa-624da4b28450",


so this thing, we can now provide to it dynamically from the jenkins pipeline while triggering..
3878909f-e2f8-4588-b8fa-624da4b28450

I know in the tenat ID, we usually have only this value: 3878909f

but we somehow want to make the lambda act like this: 3878909f-*

so basically, it shouldn't care what's in front of that value and it should bring the absolute value first and then filter.



  
