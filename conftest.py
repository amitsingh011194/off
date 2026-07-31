Hi Team,

We’ve set up an automated weekly AWS cost summary for Paymentor platforms. Starting [week of DATE / next scheduled run: Monday mornings], you’ll receive these reports by email — no manual action needed.

I’ve attached sample PROD email screenshots from each platform (PCAAS US, FDR, LFS, and HSBC) so you can see the format, layout, and level of detail before the first live run.
What this is
A Jenkins automation runs every Monday and collects AWS spend across accross multiple tenants. It sends a weekly cost summary email per environment (dev, uat, prod) with an Excel attachment for full details.
This covers:
Platform
Scope
PCAAS US
All PCAAS US tenants (dev / uat / prod)
FDR
FDR platform (dev / uat / prod)
LFS
LFS platform (dev / uat / prod)
HSBC
HSBC tenants — hsbcinm & hsbcmyh (dev / uat / prod)
What you’ll receive
One email per environment (e.g. dev, uat, prod), with:
Subject format:
Weekly Cost Summary | [start date] to [end date] | [Platform] | [ENV] | AWS Account [account ID]
Example: Weekly Cost Summary | 2026-07-01 to 2026-07-29 | PCAAS US | PROD | AWS Account 016795361898
Email body:
Grand total spend for that environment (month-to-date)
Time range: 1st of the month through the report date
Per-tenant breakdown, sorted by highest spend first
Top 5 services per tenant (highlighted)
“Other services” row when a tenant has more than 5 services
Untagged resources section where applicable
Excel attachment (weekly-cost-report-{env}.xlsx):
Summary — tenant totals, usage %, service count
Details — full service-level breakdown, tenant sections, top 5 highlighted
The attached screenshots show PROD examples for each platform — same structure you’ll get for dev and uat as well.
Reporting period
Costs are month-to-date, not just the past week.
Example: a report on 29 July covers 1 July – 29 July in the platform’s local timezone.
Who receives it
Reports go to the configured distribution list (DevOps / platform leads). If you need to be added or removed, contact [your name / team email].
Please review the attached PROD samples and share any feedback before [date / first production run].

Thanks,
Amit Singh


Get Outlook for Mac
