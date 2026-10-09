# Shared Terragrunt root configuration.
#
# State bucket/lock-table naming follows the sibling `ec1h-go-n-pay-admin-portal`
# repository, which deploys into the same non-prod AWS account (905418043725)
# under the same "csd" project prefix. `ec1h-shared-iac` uses a different
# per-account bucket convention that belongs to a different AWS account -
# that convention was deliberately not copied here. Confirm this bucket/table
# already exists (or create it) before any real `terragrunt init`.

locals {
  project_name = "csd"
  aws_region   = "af-south-1"

  account_vars     = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  environment_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))

  account_id  = local.account_vars.locals.aws_account_id
  environment = local.environment_vars.locals.environment

  state_bucket_name = try(local.environment_vars.locals.state_bucket_name, "${local.project_name}-terraform-backend-${local.environment}-${local.aws_region}-bucket")
  state_key         = try(local.environment_vars.locals.state_key, "${local.project_name}/${local.environment}/${path_relative_to_include()}/terraform.tfstate")
  lock_table_name   = try(local.environment_vars.locals.lock_table_name, "${local.project_name}-terraform-state-${local.environment}-${local.aws_region}-lock")

  common_vars = {
    aws_region   = local.aws_region
    project_name = local.project_name
    default_tags = tomap({
      "Project"     = local.project_name
      "Environment" = local.environment
      "ManagedBy"   = "Terragrunt"
    })
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
}
EOF
}

generate "versions" {
  path      = "versions.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.11.4"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.18.0"
    }
  }
}
EOF
}

remote_state {
  backend = "s3"
  config = {
    encrypt        = true
    bucket         = local.state_bucket_name
    key            = local.state_key
    region         = local.aws_region
    dynamodb_table = local.lock_table_name
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

inputs = merge(
  local.account_vars.locals,
  local.environment_vars.locals,
  local.common_vars,
)
