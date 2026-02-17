resource "aws_lambda_permission" "lambda_gate_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-skeps-gatekeeper"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_data_loader_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-skeps-selective-data-loader"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_etl_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-skeps-etl"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_datachecks_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-skeps-datachecks"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_file_merge_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-skeps-file-merger"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_forwardflow_savefile_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-af_forwardflow_savefile"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "fnbo_permission" {
  statement_id  = "AllowExecutionFromEventBridgeFnbo"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_deferred_loans_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.fnbo_rule.arn
}

# FNBO permission
resource "aws_lambda_permission" "allow_eventbridge_invoke_fnbo" {
  count = var.customer_id == "fnbo" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeFnbo"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_misc_code_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bureau_tagging_misc_code_update_fnbo.arn
}

# AF permission
resource "aws_lambda_permission" "allow_eventbridge_invoke_af" {
  count = var.customer_id == "fnbo" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeAf"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_misc_code_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bureau_tagging_misc_code_update_af.arn
}

# UCL permission
resource "aws_lambda_permission" "allow_eventbridge_invoke_ucl" {
  count = var.customer_id == "fnbo" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeUcl"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_misc_code_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bureau_tagging_misc_code_update_ucl.arn
}


resource "aws_lambda_permission" "af_permission" {
  count = var.customer_id == "fnbo" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeAf"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_deferred_loans_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.af_rule.arn
}

resource "aws_lambda_permission" "ucl_permission" {
  count = var.customer_id == "fnbo" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeUcl"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-bureau_tagging_deferred_loans_update"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ucl_rule.arn
}


resource "aws_lambda_permission" "lambda_paper_statement_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-af-paper-statement"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_clp_ach_reconciliation_report_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-clp-ach-reconciliation-report"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_clp_ach_api_reconciliation_report_permission" {
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-clp-ach-api-reconciliation-report"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}

resource "aws_lambda_permission" "lambda_activity_file_formatter_permission" {
  statement_id  = "AllowExecutionFromEventBridgeActivityFile"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-activity-file-formatter"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.activity_file_formatter_schedule.arn
}

resource "aws_lambda_permission" "lambda_activity_file_formatter_permission_sunday" {
  statement_id  = "AllowExecutionFromEventBridgeActivityFileSunday"
  action        = "lambda:InvokeFunction"
  function_name = "tops-etl-${var.environment}-activity-file-formatter"
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.activity_file_formatter_schedule_sunday.arn
}

resource "aws_lambda_permission" "lambda_agency_posting" {
  statement_id  = "AllowExecutionFromAgencyPosting"
  action        = "lambda:InvokeFunction"
  function_name = "pos-techops-serverless-${var.environment}-agencyPostingHandler"
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.customer_id}-tops-${var.environment}-s3-dps"
}
