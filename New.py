import boto3
import os
from datetime import date
 
ce = boto3.client('ce')
 
LIMIT = float(os.environ.get("LIMIT", 1000))
TAG_KEY = "sb:cost:tenant"
 
 
# ---------------------------------------------------
# GET ALL TAGS
# ---------------------------------------------------
def get_all_tenant_tags(start, end):
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
 
    return sorted(set(all_tags))
 
 
# ---------------------------------------------------
# GET COST GROUPED BY SERVICE + TAG
# ---------------------------------------------------
def get_cost_grouped(start, end):
    return ce.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "TAG", "Key": TAG_KEY}
        ]
    )
 
 
# ---------------------------------------------------
# LAMBDA HANDLER
# ---------------------------------------------------
def lambda_handler(event, context):
    try:
        tenant_prefix = event.get("tenant_prefix")
 
        if not tenant_prefix:
            raise ValueError("tenant_prefix is required")
 
        start = date.today().replace(day=1).strftime('%Y-%m-%d')
        end = date.today().strftime('%Y-%m-%d')
 
        print(f"Execution for prefix: {tenant_prefix}")
 
        # =====================================================
        # STEP 1: ALL TAG VALUES
        # =====================================================
        all_tags = get_all_tenant_tags(start, end)
 
        matched_tenants = [
            t for t in all_tags
            if t.startswith(tenant_prefix)
        ]
 
        # =====================================================
        # STEP 2: COST DATA (TAG + SERVICE)
        # =====================================================
        response = get_cost_grouped(start, end)
 
        tenant_breakdown = {}
        total_tagged_cost = 0
 
        unallocated_breakdown = {}
        total_unallocated_cost = 0
 
        results = response.get('ResultsByTime', [])
 
        if results:
            for group in results[0].get('Groups', []):
 
                service = group['Keys'][0]
                tag_value = group['Keys'][1] if len(group['Keys']) > 1 else None
 
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
 
                # =====================================================
                # UNALLOCATED = NO TAG VALUE (THIS IS THE KEY FIX)
                # =====================================================
                if tag_value is None or tag_value == "":
                    unallocated_breakdown[service] = round(
                        unallocated_breakdown.get(service, 0) + cost, 2
                    )
                    total_unallocated_cost += cost
 
                else:
                    tenant_breakdown[service] = round(
                        tenant_breakdown.get(service, 0) + cost, 2
                    )
                    total_tagged_cost += cost
 
        # =====================================================
        # FINAL TOTAL
        # =====================================================
        total_spend = round(total_tagged_cost + total_unallocated_cost, 2)
        usage_percent = round((total_spend / LIMIT) * 100, 2) if LIMIT else 0
 
        # =====================================================
        # RESPONSE
        # =====================================================
        return {
            "statusCode": 200,
            "body": {
                "tenant_prefix": tenant_prefix,
                "all_tag_values": all_tags,
                "matched_tenants": matched_tenants,
 
                "total_spend": total_spend,
                "usage_percent": usage_percent,
 
                "tenant_service_breakdown": tenant_breakdown,
                "unallocated_service_breakdown": unallocated_breakdown,
 
                "unallocated_cost": round(total_unallocated_cost, 2)
            }
        }
 
    except Exception as e:
        print(f"Error: {str(e)}")
        raise


my idea is that, lets seperate both and create two lambdas., one should handle the tagged resources and the other should handle the untagged resources.

I have already create two lambdas. the one I am sharing is supposed to handle only  the untagged resources.

I have already tested it out and its pretty much working as expected. 

here's the payload I used:
{
  "tenant_prefix": " "
}


and I got my desired reponse as well which I will share now. 
Hold on until I share all the details. lets get this lambda working as expected first.
