
# fnbo and af s3 triggers go here
resource "aws_s3_bucket_notification" "skeps_gatekeeper_bucket_fnbo" {
  bucket = "${var.customer_id}-tops-${var.environment}-s3-dps"

  count = var.customer_id == "fnbo" ? 1 : 0

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-gatekeeper"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/fnbo/etl/original-files/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-etl"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/fnbo/etl/manageable-files/etl/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-datachecks"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/fnbo/etl/manageable-files/datacheck/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-selective-data-loader"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/fnbo/etl/process-start/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-file-merger"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/fnbo/etl/manageable-files/file-merger/"
  } 

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-gatekeeper"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/etl/original-files/"
  }
  
  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-etl"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/etl/manageable-files/etl/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-datachecks"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/etl/manageable-files/datacheck/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-selective-data-loader"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/etl/process-start/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-file-merger"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/etl/manageable-files/file-merger/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-af_forwardflow_savefile"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/legacy/forward-flow/"
  }
  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-af-paper-statement"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/reports/paper_statement/ps_start/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-gatekeeper"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/etl/original-files/"
  }
  
  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-etl"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/etl/manageable-files/etl/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-datachecks"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/etl/manageable-files/datacheck/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-selective-data-loader"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/etl/process-start/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-file-merger"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/etl/manageable-files/file-merger/"
  }

  lambda_function {
     lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:pos-techops-serverless-${var.environment}-agencyPostingHandler"
     events              = ["s3:ObjectCreated:*"]
     filter_prefix       = "clients/fnbo/agencyFiles/process_start"
     filter_suffix       = ".csv"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:pos-techops-serverless-${var.environment}-agencyPostingHandler"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/af/agencyFiles/process_start"
    filter_suffix       = ".csv"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:pos-techops-serverless-${var.environment}-agencyPostingHandler"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/ucl/agencyFiles/process_start"
    filter_suffix       = ".csv"
  }

  depends_on = [
    module.deploy_lambdas,
    aws_lambda_permission.lambda_gate_permission,
    aws_lambda_permission.lambda_etl_permission,
    aws_lambda_permission.lambda_datachecks_permission,
    aws_lambda_permission.lambda_data_loader_permission,
    aws_lambda_permission.lambda_file_merge_permission,
    aws_lambda_permission.lambda_forwardflow_savefile_permission,
    aws_lambda_permission.lambda_paper_statement_permission,
    aws_lambda_permission.lambda_agency_posting
  ]
}
# other customer triggers go here
resource "aws_s3_bucket_notification" "skeps_gatekeeper_bucket_customers" {
  bucket = "${var.customer_id}-tops-${var.environment}-s3-dps"

  count = var.customer_id != "fnbo" ? 1 : 0

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-gatekeeper"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/etl/original-files/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-etl"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/etl/manageable-files/etl/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-datachecks"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/etl/manageable-files/datacheck/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-selective-data-loader"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/etl/process-start/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-skeps-file-merger"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/etl/manageable-files/file-merger/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-clp-ach-reconciliation-report"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/outbound/servicing/nacha/"
  }

  lambda_function {
    lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:tops-etl-${var.environment}-clp-ach-api-reconciliation-report"
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "clients/${var.customer_id}/reports/ach_reconciliation_report/ps_start/"
  }

  lambda_function {
     lambda_function_arn = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:pos-techops-serverless-${var.environment}-agencyPostingHandler"
     events              = ["s3:ObjectCreated:*"]
     filter_prefix       = "clients/${var.customer_id}/agencyFiles/process_start"
     filter_suffix       = ".csv"
  }

  depends_on = [
    module.deploy_lambdas,
    aws_lambda_permission.lambda_gate_permission,
    aws_lambda_permission.lambda_etl_permission,
    aws_lambda_permission.lambda_datachecks_permission,
    aws_lambda_permission.lambda_data_loader_permission,
    aws_lambda_permission.lambda_file_merge_permission,
    aws_lambda_permission.lambda_paper_statement_permission,
    aws_lambda_permission.lambda_clp_ach_reconciliation_report_permission,
    aws_lambda_permission.lambda_clp_ach_api_reconciliation_report_permission

  ]
}
