Great — that's a solid set of Terraform interview questions that test both conceptual understanding and real-world experience. Below, I’ll enhance each question with a sample answer or additional follow-up prompts you can use to dig deeper during the interview.

✅ Enhanced Terraform Interview Questions with Guidance

1. You accidentally deleted a resource from the cloud console but it still exists in the state file. What steps would you take to reconcile this?
✅ Expected Answer:
* Run terraform plan — it will show the resource as needing recreation.
* Run terraform apply — Terraform will recreate the missing resource.
* Alternatively, if you don't want to recreate it, run terraform state rm to remove the reference from the state.
🧠 Follow-up Prompt:
* What if the resource is complex and you don't want to recreate it?

2. Is it possible to apply Terraform without a state file? What are the limitations or risks of attempting this?
✅ Expected Answer:
* Technically yes, but Terraform needs a state to track resource IDs and properties.
* Without a state file:
    * Terraform won't know what exists.
    * It may try to recreate everything.
    * You lose the ability to detect drift.
* It breaks the declarative model.
🧠 Follow-up Prompt:
* How would you handle a lost or corrupted state file?

3. Could you write down a basic declarative pipeline structure and some of the stages?
✅ Expected Structure:
pipeline {
  agent any
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Terraform Init') {
      steps { sh 'terraform init' }
    }
    stage('Terraform Validate') {
      steps { sh 'terraform validate' }
    }
    stage('Terraform Plan') {
      steps { sh 'terraform plan -out=tfplan' }
    }
    stage('Terraform Apply') {
      when { branch 'main' }
      steps { sh 'terraform apply -auto-approve tfplan' }
    }
  }
}
🧠 Follow-up Prompt:
* How do you prevent two pipelines from running terraform apply at the same time?

4. Suppose you apply Terraform, and someone else changes the resource in the console. What happens?
✅ Expected Answer:
* This causes drift.
* The next terraform plan will detect the difference between desired and actual state.
* Terraform will attempt to revert or reconcile the change depending on configuration.
🧠 Follow-up Prompt:
* What if the change is to a tag? What if it's a required property?

5. You change a resource manually in the AWS Console. How do you reconcile this with Terraform?
✅ Answer:
* Run terraform plan to see the difference.
* Then:
    * Use terraform apply to revert the change (if Terraform should control it).
    * Use terraform refresh or apply -refresh-only to accept the manual change.
    * Optionally, update your .tf files if the manual change is now intended.

6. What is terraform output used for? And what's the difference between a local variable and a Terraform variable?
✅ Expected Answer:
* terraform output shows defined outputs — useful for passing values (e.g., IP addresses) to other tools or scripts.
* variable (with var.) is user-defined input.
* locals are computed values within the module — reusable constants or derived expressions.
🧠 Follow-up Prompt:
* When would you prefer local over output?

7. What is a .tfvars file used for? What's the difference between .tfvars and variables.tf?
✅ Expected Answer:
* variables.tf (or vars.tf) defines the variable schema: name, type, description, default.
* .tfvars provides actual values to those variables (e.g., region = "us-west-2").
* Allows separation of config from code.
🧠 Follow-up Prompt:
* How do you pass .tfvars in CI/CD pipelines?

8. What is a Terraform module and why is it used?
✅ Expected Answer:
* A module is a reusable block of Terraform code.
* Promotes DRY (Don't Repeat Yourself) principles.
* Makes complex infra manageable and testable.
🧠 Follow-up Prompt:
* What's the difference between a root module and a child module?
* How do you pass outputs between modules?

9. What are different ways of running Terraform code in your Jenkins pipeline?
✅ Expected Answer:
* Inline shell steps in Jenkinsfile (sh 'terraform plan')
* Use shared Jenkins libraries to wrap Terraform logic.
* Use Terraform Cloud or CLI via Docker agents.
* Use workspaces or parameterized builds for different environments.
* Ensure remote backend for state and use of locks (e.g., S3 + DynamoDB).
🧠 Follow-up Prompt:
* How do you manage secrets in this pipeline?
* How do you trigger Terraform only on relevant changes?

Would you like me to create a printable/interview-friendly version of this? Or would you like mock answers you can use to calibrate the candidate’s level?
Great — that's a solid set of Terraform interview questions that test both conceptual understanding and real-world experience. Below, I’ll enhance each question with a sample answer or additional follow-up prompts you can use to dig deeper during the interview.

✅ Enhanced Terraform Interview Questions with Guidance

1. You accidentally deleted a resource from the cloud console but it still exists in the state file. What steps would you take to reconcile this?
✅ Expected Answer:
	•	Run terraform plan — it will show the resource as needing recreation.
	•	Run terraform apply — Terraform will recreate the missing resource.
	•	Alternatively, if you don't want to recreate it, run terraform state rm to remove the reference from the state.
🧠 Follow-up Prompt:
	•	What if the resource is complex and you don't want to recreate it?

2. Is it possible to apply Terraform without a state file? What are the limitations or risks of attempting this?
✅ Expected Answer:
	•	Technically yes, but Terraform needs a state to track resource IDs and properties.
	•	Without a state file:
	◦	Terraform won't know what exists.
	◦	It may try to recreate everything.
	◦	You lose the ability to detect drift.
	•	It breaks the declarative model.
🧠 Follow-up Prompt:
	•	How would you handle a lost or corrupted state file?

3. Could you write down a basic declarative pipeline structure and some of the stages?
✅ Expected Structure:
pipeline {
  agent any
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Terraform Init') {
      steps { sh 'terraform init' }
    }
    stage('Terraform Validate') {
      steps { sh 'terraform validate' }
    }
    stage('Terraform Plan') {
      steps { sh 'terraform plan -out=tfplan' }
    }
    stage('Terraform Apply') {
      when { branch 'main' }
      steps { sh 'terraform apply -auto-approve tfplan' }
    }
  }
}
🧠 Follow-up Prompt:
	•	How do you prevent two pipelines from running terraform apply at the same time?

4. Suppose you apply Terraform, and someone else changes the resource in the console. What happens?
✅ Expected Answer:
	•	This causes drift.
	•	The next terraform plan will detect the difference between desired and actual state.
	•	Terraform will attempt to revert or reconcile the change depending on configuration.
🧠 Follow-up Prompt:
	•	What if the change is to a tag? What if it's a required property?

5. You change a resource manually in the AWS Console. How do you reconcile this with Terraform?
✅ Answer:
	•	Run terraform plan to see the difference.
	•	Then:
	◦	Use terraform apply to revert the change (if Terraform should control it).
	◦	Use terraform refresh or apply -refresh-only to accept the manual change.
	◦	Optionally, update your .tf files if the manual change is now intended.

6. What is terraform output used for? And what's the difference between a local variable and a Terraform variable?
✅ Expected Answer:
	•	terraform output shows defined outputs — useful for passing values (e.g., IP addresses) to other tools or scripts.
	•	variable (with var.) is user-defined input.
	•	locals are computed values within the module — reusable constants or derived expressions.
🧠 Follow-up Prompt:
	•	When would you prefer local over output?

7. What is a .tfvars file used for? What's the difference between .tfvars and variables.tf?
✅ Expected Answer:
	•	variables.tf (or vars.tf) defines the variable schema: name, type, description, default.
	•	.tfvars provides actual values to those variables (e.g., region = "us-west-2").
	•	Allows separation of config from code.
🧠 Follow-up Prompt:
	•	How do you pass .tfvars in CI/CD pipelines?

8. What is a Terraform module and why is it used?
✅ Expected Answer:
	•	A module is a reusable block of Terraform code.
	•	Promotes DRY (Don't Repeat Yourself) principles.
	•	Makes complex infra manageable and testable.
🧠 Follow-up Prompt:
	•	What's the difference between a root module and a child module?
	•	How do you pass outputs between modules?

9. What are different ways of running Terraform code in your Jenkins pipeline?
✅ Expected Answer:
	•	Inline shell steps in Jenkinsfile (sh 'terraform plan')
	•	Use shared Jenkins libraries to wrap Terraform logic.
	•	Use Terraform Cloud or CLI via Docker agents.
	•	Use workspaces or parameterized builds for different environments.
	•	Ensure remote backend for state and use of locks (e.g., S3 + DynamoDB).
🧠 Follow-up Prompt:
	•	How do you manage secrets in this pipeline?
	•	How do you trigger Terraform only on relevant changes?

Would you like me to create a printable/interview-friendly version of this? Or would you like mock answers you can use to calibrate the candidate’s level?


————-



Great question! Understanding the difference between a root module and a child module in Terraform is key to managing scalable infrastructure.

✅ Root Module vs Child Module in Terraform

🔹 1. Root Module
* The root module is the main Terraform configuration where you run Terraform commands like terraform init, terraform plan, and terraform apply.
* It includes all .tf files in the working directory where Terraform is executed.
🧾 Example: If your directory has:
main.tf
variables.tf
outputs.tf
And you run terraform apply in that folder — this is your root module.

🔹 2. Child Module
* A child module is a reusable piece of Terraform code that is called by another module — usually the root module.
* It can be local (in a subdirectory) or remote (from GitHub, Terraform Registry, etc.).
* Child modules encapsulate logic like creating VPCs, EC2 instances, etc.
🧾 Example:
module "vpc" {
  source = "./modules/vpc"
  cidr_block = "10.0.0.0/16"
}
In this example:
* The root module is calling a child module located at ./modules/vpc.

📌 Key Differences
Feature	Root Module	Child Module
Location	Where Terraform CLI is executed	Called from the root or another module
Purpose	Coordinates everything (entry point)	Encapsulates logic for reuse
Execution Context	Has full access to all providers, configs	Runs within context of calling module
Examples	main.tf, variables.tf in top folder	vpc/, ec2/ inside modules/
🧠 Interview Insight:
You can ask:
* How do you share outputs from a child module to another?
* Can a child module call another child module?
* What are the benefits of using modules in a team environment?

Let me know if you want a diagram or example code structure to better visualize the root vs child modules.


———

What is the difference between script and steps in a Jenkinsfile?

———-


How do you use environment variables in Jenkins pipelines?


—————

How would you trigger a pipeline automatically when there is an event took place in github?

———-


What is a jenkins workspace?

—————

🔹 17. What’s the use of post blocks in Jenkins?
Answer: To define actions that run after a stage or pipeline, regardless of success or failure. E.g., notifications, cleanup, archiving.



🔹 18. What is parallel execution in Jenkins pipelines?
Answer: Allows multiple stages or tasks to run at the same time to speed up builds/tests.
🧾 Example:
groovy
Copy code
parallel {
  stage('Test1') { steps { ... } }
  stage('Test2') { steps { ... } }
}


What are different type of load balancers in aws and also tell me what is the difference between them?


Cloudfront- what is path based routing?


Basic docker file steps?
