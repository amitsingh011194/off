How Route 53, MX, DKIM, and SES fit together
HSBC PH UAT example. Same shape in DEV and PROD — only the host name and account change. All of this is DNS + SES. S3 is just where SES drops the file after mail is accepted.

One line
The hosted zone is the address book. MX tells senders “deliver mail to SES.” DKIM CNAMEs tell SES “this AWS account owns that name.” SES is the mail server. None of these is an Outlook mailbox.
1. The map
2. When someone sends mail
3. One-time setup
Two different questions, same zone
Route 53 does not receive mail and does not store files. It only answers DNS lookups. SES and the sender ask it different questions.

Question A — the sender
Who accepts mail for ph.hsbc.uat-paymentor.exlservice.com?

Outlook / HSBC looks up an MX record. The zone answers with Amazon’s receive host. Then the sender delivers the message to SES over SMTP. This happens on every send.

Record: ph → 10 inbound-smtp.us-east-1.amazonaws.com

Question B — Amazon SES
Does this AWS account own that hostname?

SES looks up three _domainkey names. If they alias to amazonses.com, the identity stays Verified. This is not the mail path. It is ownership proof (and later, outbound signing).

Three CNAMEs generated when the identity was created

The hosted zone is just this folder
Zone name hsbc.uat-paymentor.exlservice.com. Record names inside it are relative. The row named ph is the host ph.hsbc.uat-paymentor.exlservice.com.

Route 53 hosted zone

hsbc.uat-paymentor.exlservice.com

ph

Mail delivery

10 inbound-smtp.us-east-1.amazonaws.com

kon2jye2qnxarhreu2wld2mhzroabu23._domainkey.ph

Ownership / DKIM

kon2jye2qnxarhreu2wld2mhzroabu23.dkim.amazonses.com

mdsq5c4ud4a3imf2ixfkss47egbrqawc._domainkey.ph

Ownership / DKIM

mdsq5c4ud4a3imf2ixfkss47egbrqawc.dkim.amazonses.com

qg4bfel3qp4l45i5qmilfitzlah7teqt._domainkey.ph

Ownership / DKIM

qg4bfel3qp4l45i5qmilfitzlah7teqt.dkim.amazonses.com

Other records already in this zone (ACM, Imperva, hsbcph) stay untouched. They are unrelated to this file drop.

Piece	Where it lives	Job
Hosted zone	Route 53	DNS folder for hsbc.uat-paymentor.exlservice.com. Holds MX + CNAMEs. Not a mailbox.
MX record	Inside the zone	Tells senders to deliver to inbound-smtp.us-east-1.amazonaws.com
DKIM CNAMEs (3)	Inside the zone	Prove this account owns ph.… so SES can verify the identity
SES identity	SES (not Route 53)	The AWS object for ph.hsbc.uat-paymentor.exlservice.com. Verified after those CNAMEs resolve.
Receipt rule	SES (Terraform)	If To: matches paymentor.hsbcph.uat@ph.hsbc.uat-paymentor.exlservice.com, PutObject to S3 etl/email-inbound/


How Route 53, MX, DKIM, and SES fit together
HSBC PH UAT example. Same shape in DEV and PROD — only the host name and account change. All of this is DNS + SES. S3 is just where SES drops the file after mail is accepted.

One line
The hosted zone is the address book. MX tells senders “deliver mail to SES.” DKIM CNAMEs tell SES “this AWS account owns that name.” SES is the mail server. None of these is an Outlook mailbox.
1. The map
2. When someone sends mail
3. One-time setup
What happens on every email
DKIM CNAMEs are not in this path. The sender never looks them up. Only MX is queried at send time.

Outlook / HSBC
Sends to the mailbox
Route 53 MX
Where does mail go?
SES inbound
inbound-smtp us-east-1
Receipt rule
Match To: address
Tenant S3
etl/email-inbound/
1
Send

Someone sends to paymentor.hsbcph.uat@ph.hsbc.uat-paymentor.exlservice.com. Outlook does not know AWS. It only has an email address.

2
MX lookup

The sending mail server asks DNS: MX for ph.hsbc.uat-paymentor.exlservice.com? Route 53 answers inbound-smtp.us-east-1.amazonaws.com.

3
SES accepts

That hostname is Amazon’s receive endpoint in N. Virginia. Mail arrives in the HSBC UAT account. The identity for ph.… must already be Verified (from the DKIM CNAMEs, done earlier).

4
Receipt rule

The active rule set looks at To:. If it matches the configured recipient, SES writes the raw .eml to the tenant bucket under etl/email-inbound/, encrypted with the tenant CMK.

If MX is missing or points at Office 365
Mail never reaches SES. That is the @opiglobal.com bounce (550 5.1.10). S3 stays empty except for SES’s own tiny setup probe.


 What we did once (not on every email)
Identity + DKIM CNAMEs + MX. Terraform did not create these. Console (UAT) or Jenkins AWS CLI (prod). Receipt rule was a separate Jenkins Terraform apply.

A. Verify the identity with DKIM
Create identity
SES · Domain · Easy DKIM
SES generates 3 names
Only inside SES so far
Put CNAMEs in zone
Now they are real DNS
Identity Verified
DKIM Successful
SES then looks up those three names in DNS. If they match, the Authentication tab shows DKIM Successful. The blue “publish these CNAMEs, may take 72 hours” box is leftover help text — not a failure once status is Successful.

B. Add MX in the same zone
Separate record, same folder. Type MX, name ph, value 10 inbound-smtp.us-east-1.amazonaws.com. This is what senders use.

C. Receipt rule (Terraform, not Route 53)
After mail can reach SES, the rule says what to do with it: store in S3. Cloud already allowed ses.amazonaws.com to PutObject and use the CMK.

Do this	Skip this
Edit the live hosted zone (NS matches public DNS)	The empty duplicate zone with the same domain name
Keep MX and the three DKIM CNAMEs	Deleting CNAMEs — identity verification can fail again
Use the ph.hsbc.{env}-paymentor.exlservice.com host	@opiglobal.com — that MX belongs to Office 365
