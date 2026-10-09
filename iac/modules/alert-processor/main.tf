data "aws_caller_identity" "current" {}

locals {
  name = "${var.project_name}-${var.component_name}-${var.environment}"
  tags = merge(var.default_tags, var.tags)

  # Adopted stacks pass their existing names so nothing is replaced.
  lambda_function_name = coalesce(var.lambda_function_name, local.name)
  lambda_role_name     = coalesce(var.lambda_role_name, local.name)
  lambda_policy_name   = coalesce(var.lambda_policy_name, "${local.name}-policy")
  dynamodb_table_name  = coalesce(var.dynamodb_table_name, "${local.name}-dedup")
  api_name             = coalesce(var.api_name, local.name)
}

# Existing resources adopted from the legacy stack (state key
# csd/m2c-alert-integration/terraform.tfstate). These only rename addresses
# in state; they never touch AWS.
moved {
  from = aws_apigatewayv2_api.m2c_alerts
  to   = aws_apigatewayv2_api.this
}

moved {
  from = aws_apigatewayv2_route.post_alerts
  to   = aws_apigatewayv2_route.alerts
}

moved {
  from = aws_cloudwatch_log_group.api_gateway
  to   = aws_cloudwatch_log_group.api_gateway_access_logs
}

moved {
  from = aws_iam_role.lambda_exec
  to   = aws_iam_role.lambda
}

moved {
  from = aws_lambda_function.alert_processor
  to   = aws_lambda_function.this
}

resource "aws_dynamodb_table" "dedup" {
  name         = local.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "fingerprint"

  attribute {
    name = "fingerprint"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  # Holds live dedup state; a bad plan must never delete it.
  lifecycle {
    prevent_destroy = true
  }

  tags = local.tags
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = local.lambda_role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = local.tags
}

# One policy, matching the live stack: log writes for this function only and
# point read/write on its own table. Scan and Delete are intentionally
# excluded (the reconciliation tool uses a separate, read-only identity).
data "aws_iam_policy_document" "lambda_permissions" {
  statement {
    sid       = "AllowCloudWatchLogs"
    effect    = "Allow"
    actions   = ["logs:PutLogEvents", "logs:CreateLogStream"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  statement {
    sid       = "AllowDynamoDBDedup"
    effect    = "Allow"
    actions   = ["dynamodb:UpdateItem", "dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.dedup.arn]
  }
}

resource "aws_iam_policy" "lambda_permissions" {
  name   = local.lambda_policy_name
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

resource "aws_iam_role_policy_attachment" "lambda_permissions" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_permissions.arn
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.lambda_log_retention_days
  tags              = local.tags
}

resource "aws_lambda_function" "this" {
  function_name = local.lambda_function_name
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.lambda_runtime
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout

  # Deploys the exact zip built and tested by build.yml and attached to a
  # release; Terraform never builds code itself.
  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  environment {
    variables = {
      HALO_BASE_URL       = var.halo_base_url
      HALO_TICKET_TYPE_ID = tostring(var.halo_ticket_type_id)
      HALO_TEAM_EC1       = tostring(var.halo_team_ec1)
      HALO_TEAM_JW        = tostring(var.halo_team_jw)
      HALO_TEAM_INTERNAL  = tostring(var.halo_team_internal)
      DYNAMODB_TABLE      = aws_dynamodb_table.dedup.name
      DYNAMODB_TTL_DAYS   = tostring(var.dynamodb_ttl_days)
    }
  }

  # HALO_CLIENT_ID, HALO_CLIENT_SECRET and WEBHOOK_SECRET are set on the live
  # function out-of-band and must never pass through Terraform code, state
  # inputs or CI logs. Ignoring the block keeps them (and the live values of
  # the settings above) untouched; moving them to Secrets Manager is a
  # follow-up.
  lifecycle {
    ignore_changes = [environment]
  }

  # API Gateway invokes this synchronously (RequestResponse) - a Lambda DLQ or
  # on-failure destination only applies to async invocations, so it would
  # never fire here. Failure visibility instead comes from the handler's
  # non-2xx response contract (see src/handlers/alert-processor/lambda_function.py) plus the
  # HaloRequestFailure/UnmappedAlertType alarms in monitoring.tf.

  tags = local.tags

  depends_on = [aws_cloudwatch_log_group.lambda]
}
