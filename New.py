data "aws_caller_identity" "current" {}

resource "aws_iam_role" "lambda_iam_role" {
  name = "lambda-${var.lambda_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })

  # inline_policy {
  #   name = "${var.customer}-ssp-${var.env}-lambda-${var.lambda_name}-inline-policy"

  #   policy = file("${var.lambda_path}/iam_policy.json")
  # }
}

# resource "aws_cloudwatch_log_group" "lambda_log_group" {
#   name              = "/aws/lambda/${var.lambda_name}"
#   retention_in_days = 14
# }

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.lambda_path
  output_path = "./tmp/${var.lambda_name}.zip"
}

resource "aws_s3_object" "upload_lambda_zip" {
  bucket      = "exl-${var.customer}-${var.env}-templates"
  key         = "lambdas/${var.lambda_name}"
  source      = data.archive_file.lambda_zip.output_path
  source_hash = data.archive_file.lambda_zip.output_base64sha256
  server_side_encryption = var.kms_key_id != null ? "aws:kms" : "AES256"
  kms_key_id = var.kms_key_id 

}

resource "aws_lambda_function" "deploy_lambda" {
  function_name    = "${var.customer}-ssp-${var.env}-lambda-${var.lambda_name}"
  description      = "Created in repo loan-servicing-api commit:${var.commit_id} branch:${var.branch} " 
  role             = aws_iam_role.lambda_iam_role.arn
  handler          = (
    var.lambda_name == "${var.customer}-ivr-processing" || 
    var.lambda_name == "${var.customer}-ivr-tabapay-call" ||
    var.lambda_name == "${var.customer}-ivr-conduent-call" || 
    var.lambda_name == "${var.customer}-campaign-activity-code" ||
    var.lambda_name == "${var.customer}-campaign-customer-profiles" ||
    var.lambda_name == "${var.customer}-ivr-ssp-integration" ||
    var.lambda_name == "${var.customer}-campaign-customerdata-manupulation" ||
    var.lambda_name == "${var.customer}-campaign-database-update" ||
    var.lambda_name == "${var.customer}-campaign-run-status" ||
    var.lambda_name == "${var.customer}-campaign-lambda" || 
    var.lambda_name == "${var.customer}-campaign-profiles-manupulation"
  ) ? "lambda_function.lambda_handler" : "index.lambda_handler"
  runtime          = (
    var.lambda_name == "${var.customer}-ivr-processing" || 
    var.lambda_name == "${var.customer}-ivr-tabapay-call" ||
    var.lambda_name == "${var.customer}-ivr-conduent-call" || 
    var.lambda_name == "${var.customer}-campaign-activity-code" ||
    var.lambda_name == "${var.customer}-campaign-customer-profiles" ||
    var.lambda_name == "${var.customer}-ivr-ssp-integration" ||
    var.lambda_name == "${var.customer}-campaign-customerdata-manupulation" ||
    var.lambda_name == "${var.customer}-campaign-database-update" ||
    var.lambda_name == "${var.customer}-campaign-run-status" ||
    var.lambda_name == "${var.customer}-campaign-lambda" || 
    var.lambda_name == "${var.customer}-campaign-profiles-manupulation"
  ) ? "python3.10" : "nodejs20.x"
  memory_size      = 5120
  timeout          = 600
  s3_bucket        = "exl-${var.customer}-${var.env}-templates"
  s3_key           = "lambdas/${var.lambda_name}"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  # Conditionally set layers only if the lambda is "${var.customer}-ivr-tabapay-call"
  layers = ( 
    var.lambda_name == "${var.customer}-campaign-customer-profiles" || 
    var.lambda_name == "${var.customer}-ivr-tabapay-call" || 
    var.lambda_name == "${var.customer}-ivr-conduent-call" || 
    var.lambda_name == "${var.customer}-campaign-activity-code" || 
    var.lambda_name == "${var.customer}-ivr-ssp-integration" ||
    var.lambda_name == "${var.customer}-campaign-customerdata-manupulation" ||
    var.lambda_name == "${var.customer}-campaign-database-update" ||
    var.lambda_name == "${var.customer}-campaign-run-status" ||
    var.lambda_name == "${var.customer}-campaign-lambda" || 
    var.lambda_name == "${var.customer}-campaign-profiles-manupulation"
    ) ? var.lambda_layer_arns : []
    
    signing_profile_version_arn = var.code_signing_profile_arn

    dead_letter_config {
    target_arn = var.lambda_dlq_arn
  }
  reserved_concurrent_executions = var.lambda_concurrency_limit

  vpc_config {
    subnet_ids         = var.lambda_subnet_ids
    security_group_ids = var.lambda_security_group_ids
  }
  environment {
    variables = fileexists("${var.lambda_path}/env_vars.json") ? jsondecode(templatefile("${var.lambda_path}/env_vars.json", { 
            ACCOUNT_ID  = var.aws_acct_id, 
            AWS_REGION  = var.aws_region, 
            CUSTOMER_ID = var.customer, 
            ENVIRONMENT = var.environment 
          })) : {}
  }

  kms_key_arn = var.kms_key_id

  tracing_config {
    mode = "Active"
  }
  depends_on = [aws_s3_object.upload_lambda_zip]
}


resource "aws_iam_role_policy" "additional_policy" {
  count = fileexists("${var.lambda_path}/iam_policy.json") ? 1 : 0

  name   = "lambda-${var.lambda_name}-additional-policy"
  role   = aws_iam_role.lambda_iam_role.id
  policy = templatefile("${var.lambda_path}/iam_policy.json", { ACCOUNT_ID = var.aws_acct_id, AWS_REGION = var.aws_region, CUSTOMER_ID = var.customer, ENVIRONMENT = var.env, KMS_KEY_ID = var.kms_key_id})
}
