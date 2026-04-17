import boto3
import os
from datetime import date

ce = boto3.client('ce')

LIMIT = float(os.environ.get("LIMIT", 1000))
THRESHOLD = float(os.environ.get("THRESHOLD", 70))

TAG_KEY = "sb:cost:tenant"


def get_matching_tenants(prefix, start, end):
    """Fetch all tenant tag values and filter by prefix"""
    response = ce.get_tags(
        TimePeriod={'Start': start, 'End': end},
        TagKey=TAG_KEY
    )

    all_tags = response.get('Tags', [])
    print(f"All tenant tags: {all_tags}")

    matched = [t for t in all_tags if t.startswith(prefix)]

    print(f"Matched tenants for prefix '{prefix}': {matched}")

    return matched


def lambda_handler(event, context):
    try:
        # 👇 Pass prefix like "3878909f"
        tenant_prefix = event.get("tenant_prefix")

        if not tenant_prefix:
            raise ValueError("tenant_prefix is required")

        start = date.today().replace(day=1).strftime('%Y-%m-%d')
        end = date.today().strftime('%Y-%m-%d')

        print(f"Fetching cost for tenant prefix: {tenant_prefix}")

        # 🔍 Step 1: Get all matching tenants
        tenant_values = get_matching_tenants(tenant_prefix, start, end)

        if not tenant_values:
            print("No matching tenants found")
            return {
                "statusCode": 200,
                "body": {
                    "tenant_prefix": tenant_prefix,
                    "total_spend": 0,
                    "usage_percent": 0,
                    "service_breakdown": {}
                }
            }

        # -----------------------------
        # 1️⃣ TOTAL COST (Filtered tenants)
        # -----------------------------
        total_response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
           Filter={
    "Tags": {
        "Key": TAG_KEY,
        "Values": tenant_values
         }
         }
        )

        total_amount = float(
            total_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
        )

        percent = (total_amount / LIMIT) * 100 if LIMIT > 0 else 0

        # -----------------------------
        # 2️⃣ SERVICE BREAKDOWN
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
                    "Values": tenant_values
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
        # 📊 Logs
        # -----------------------------
        print("\n=== TENANT SUMMARY ===")
        print(f"Prefix: {tenant_prefix}")
        print(f"Matched Tenants: {tenant_values}")
        print(f"Total Spend: ${round(total_amount, 2)}")
        print(f"Usage: {percent:.2f}% of ${LIMIT}")

        print("\n=== SERVICE BREAKDOWN ===")
        for svc, cost in service_costs.items():
            print(f"{svc} → ${cost}")

        return {
            "statusCode": 200,
            "body": {
                "tenant_prefix": tenant_prefix,
                "matched_tenants": tenant_values,
                "total_spend": round(total_amount, 2),
                "usage_percent": round(percent, 2),
                "service_breakdown": service_costs
            }
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        raise
