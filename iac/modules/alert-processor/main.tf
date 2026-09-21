data "aws_caller_identity" "current" {}

locals {
  name = "${var.project_name}-${var.component_name}-${var.environment}"
  tags = merge(var.default_tags, var.tags)
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/.terraform/archive_files/${replace(local.name, "-", "_")}.zip"
}

# Pre-existing secret; this module only reads it (never writes secret values
# into Terraform code, variables, or outputs).
data "aws_secretsmanager_secret" "halo" {
  name = var.halo_secret_name
}

data "aws_secretsmanager_secret_version" "halo" {
  secret_id = data.aws_secretsmanager_secret.halo.id
}

locals {
  halo_secrets = jsondecode(data.aws_secretsmanager_secret_version.halo.secret_string)
}

resource "aws_dynamodb_table" "dedup" {
  name         = "${local.name}-dedup"
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

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
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
  name               = local.name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# The Lambda only needs point read/write access to its own table - Scan and
# Delete are intentionally excluded (the reconciliation tool uses a separate,
# read-only identity, not this role).
data "aws_iam_policy_document" "dynamodb_access" {
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.dedup.arn]
  }
}

resource "aws_iam_policy" "dynamodb_access" {
  name   = "${local.name}-dynamodb-access"
  policy = data.aws_iam_policy_document.dynamodb_access.json
}

resource "aws_iam_role_policy_attachment" "dynamodb_access" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.dynamodb_access.arn
}

data "aws_iam_policy_document" "secrets_access" {
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [data.aws_secretsmanager_secret.halo.arn]
  }
}

resource "aws_iam_policy" "secrets_access" {
  name   = "${local.name}-secrets-access"
  policy = data.aws_iam_policy_document.secrets_access.json
}

resource "aws_iam_role_policy_attachment" "secrets_access" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.lambda_log_retention_days
  tags              = local.tags
}

resource "aws_lambda_function" "this" {
  function_name = local.name
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.lambda_runtime
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = merge(local.halo_secrets, {
      HALO_BASE_URL       = var.halo_base_url
      HALO_TICKET_TYPE_ID = tostring(var.halo_ticket_type_id)
      HALO_TEAM_EC1       = tostring(var.halo_team_ec1)
      HALO_TEAM_JW        = tostring(var.halo_team_jw)
      HALO_TEAM_INTERNAL  = tostring(var.halo_team_internal)
      DYNAMODB_TABLE      = aws_dynamodb_table.dedup.name
      DYNAMODB_TTL_DAYS   = tostring(var.dynamodb_ttl_days)
    })
  }

  # API Gateway invokes this synchronously (RequestResponse) - a Lambda DLQ or
  # on-failure destination only applies to async invocations, so it would
  # never fire here. Failure visibility instead comes from the handler's
  # non-2xx response contract (see src/lambda_function.py) plus the
  # HaloRequestFailure/UnmappedAlertType alarms in monitoring.tf.

  tags = local.tags

  depends_on = [aws_cloudwatch_log_group.lambda]
}
