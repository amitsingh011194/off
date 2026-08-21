**From: **Amit Singh \<Amit.Singh8\@exlservice.com>
**Date: **Wednesday, 20 August 2025 at 3:55 PM
**To: **Garvit Airen \<Garvit.Airen\@exlservice.com>; Anuj Singh (Senior Executive) \<Anuj.Singh\@exlservice.com>; Sagain Saowaluck \<Sagain.Saowaluck\@exlservice.com>; Prashant Varma \<Prashant.Varma\@exlservice.com>; David Kelly \<David.Kelly\@exlservice.com>
**Cc: **Mark Sherlock \<Mark.Sherlock\@exlservice.com>; Deepanshu Agarwal \<Deepanshu.Agarwal\@exlservice.com>
**Subject: **Automation for Replicating Lambda Layers Across AWS Accounts

Hi Team,

Since we have a few new tenants getting onboarded, including some with new AWS accounts, I have developed an automation to replicate Lambda layers across accounts.

This automation will:

-Save developers from manually adding layers for every new account that gets onboarded, which is time-consuming.

-Ensure consistency across environments, making Lambda deployments smoother without layer-related issues when deploying to a new account.

-Allow developers to replicate layers from any source account to any destination account easily.


Here's the job link: [https://ucjenkinsdev.exlservice.com/job/BU/job/Digital/job/Paymentor/job/paymentor-base/job/Publish-layer-automation/](https://ucjenkinsdev.exlservice.com/job/BU/job/Digital/job/Paymentor/job/paymentor-base/job/Publish-layer-automation/)


It’s simple to use:

-Provide the **SOURCE\_ACCOUNT** (the account from which layers will be copied).
-Provide the **DEST\_ACCOUNT** (the account to which layers will be replicated).


Here’s the screenshot from the Jenkins job:

[image](cid\:image001.png@01DC11EA.1B193AD0)


To control which layers get copied, I’ve created a “Layers.txt” file where we can specify the required layer names:

[https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-paymentor-core-deploy/blob/main/deploy/legacy/Layers.txt](https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-paymentor-core-deploy/blob/main/deploy/legacy/Layers.txt)

Once the “Layers.txt” file is updated, we just need to run the Jenkins job with the source and destination accounts. The job will handle the rest:

- It will use the exact “layer version” and “Compatible runtimes” from the source account.
- It will replicate all other configurations as is, without any changes.


I have already used this automation to replicate layers from PCAAS accounts to the HSBC India account, and it is working as expected.

Please feel free to reach out if you have any questions.

Regards,
Amit Singh



so this was one automation we did and sent last year.
but post that, there have been addition in the team members, and dev teams have not really been utlising this automation and reaching out to us for the layer replication.
this was meant to be self service and should be utilised by the dev teams



so I am sending a new email to re-iterate on this so that people are utliusiung this automation 
what do I send?
