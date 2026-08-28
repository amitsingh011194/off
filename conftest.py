Hi Prashant,

It appears we won't be able to use paymentor.hsbcph.dev@opiglobal.com for receiving files.

We have already configured the SES receipt rule in the HSBC PH DEV environment. The SES, S3, and KMS integrations are working correctly, as confirmed by the successful delivery of the AMAZON_SES_SETUP_NOTIFICATION object into the tenant S3 bucket.

However, when sending a test email to paymentor.hsbcph.dev@opiglobal.com, the message bounced from Microsoft 365 with the error:

550 5.1.10 RecipientNotFound

This indicates that incoming email for the @opiglobal.com domain is still being routed through Microsoft 365 rather than Amazon SES.

Although opiglobal.com is verified in SES for outbound email (alerts and Paymentor-generated communications), domain verification alone does not enable inbound email reception. To receive mail through SES, the domain's MX records must point to SES. Updating the MX records for opiglobal.com would redirect all incoming mail away from Microsoft 365, which is not a viable option.

This is consistent with the approach used in 2023, where a dedicated EXL subdomain was created with its own MX record pointing to:

inbound-smtp.us-east-1.amazonaws.com

HSBC was then provided with an email address under that dedicated receiving subdomain.

To move forward, we will need support from the Cloud/DNS team to:

Create a dedicated receiving subdomain (for example, inbound.opiglobal.com).
Configure its MX record to point to Amazon SES (us-east-1).
Associate it with AWS account 088082905288.

Once this is in place, we can update the SES receipt rule to use:

paymentor.hsbcph.dev@<receiving-subdomain>

and perform end-to-end testing again.

Thanks,
 Amit
