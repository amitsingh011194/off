


okay lets get started. first do we need to update the lambda right?
Could you share the updated lambda to me now with all the addition.
This is the current lambda:



import boto3
import os
from datetime import date

ce = boto3.client('ce')

LIMIT = float(os.environ.get("LIMIT", 1000))
THRESHOLD = float(os.environ.get("THRESHOLD", 70))

TAG_KEY = "sb:cost:tenant"


def get_matching_tenants(prefix, start, end):
    """Fetch all tenant tag values and filter by prefix (with pagination)"""
    all_tags = []
    next_token = None

    while True:
        if next_token:
            response = ce.get_tags(
                TimePeriod={'Start': start, 'End': end},
                TagKey=TAG_KEY,
                NextPageToken=next_token
            )
        else:
            response = ce.get_tags(
                TimePeriod={'Start': start, 'End': end},
                TagKey=TAG_KEY
            )

        all_tags.extend(response.get('Tags', []))
        next_token = response.get('NextPageToken')

        if not next_token:
            break

    print(f"All tenant tags count: {len(all_tags)}")

    matched = [t for t in all_tags if t.startswith(prefix)]
    print(f"Matched tenants for prefix '{prefix}': {matched}")

    return matched


def lambda_handler(event, context):
    try:
        tenant_prefix = event.get("tenant_prefix")

        if not tenant_prefix:
            raise ValueError("tenant_prefix is required")

        start = date.today().replace(day=1).strftime('%Y-%m-%d')
        end = date.today().strftime('%Y-%m-%d')

        print(f"Fetching cost for tenant prefix: {tenant_prefix}")

        # 🔍 Step 1: Get matching tenants
        tenant_values = get_matching_tenants(tenant_prefix, start, end)

        if not tenant_values:
            print("No matching tenants found")
            return {
                "statusCode": 200,
                "body": {
                    "tenant_prefix": tenant_prefix,
                    "matched_tenants": [],
                    "total_spend": 0,
                    "usage_percent": 0,
                    "service_breakdown": {}
                }
            }

        # -----------------------------
        # 2️⃣ SERVICE BREAKDOWN + TOTAL (single API call)
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
        total_amount = 0

        results = service_response.get('ResultsByTime', [])

        if results:
            for group in results[0].get('Groups', []):
                service_name = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])

                if cost > 0:
                    rounded_cost = round(cost, 2)
                    service_costs[service_name] = rounded_cost
                    total_amount += cost

        total_amount = round(total_amount, 2)

        percent = (total_amount / LIMIT) * 100 if LIMIT > 0 else 0
        percent = round(percent, 2)

        # -----------------------------
        # 📊 Logs (for debugging only)
        # -----------------------------
        print("\n=== TENANT SUMMARY ===")
        print(f"Prefix: {tenant_prefix}")
        print(f"Matched Tenants: {tenant_values}")
        print(f"Total Spend: ${total_amount}")
        print(f"Usage: {percent}% of ${LIMIT}")

        print("\n=== SERVICE BREAKDOWN ===")
        for svc, cost in service_costs.items():
            print(f"{svc} → ${cost}")

        # -----------------------------
        # ✅ Final Response
        # -----------------------------
        return {
            "statusCode": 200,
            "body": {
                "tenant_prefix": tenant_prefix,
                "matched_tenants": tenant_values,
                "total_spend": total_amount,
                "usage_percent": percent,
                "service_breakdown": service_costs
            }
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        raise
