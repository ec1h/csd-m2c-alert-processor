locals {
  tags = tomap({
    "COST TAG 2" : "M2C Alert Processor"
  })
}

terraform {
  source = "../../../modules//alert-processor"
}

include {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  component_name = "alert-processor"

  # Release zip downloaded and checksum-verified by deploy.yml (or by hand
  # for a local plan): export LAMBDA_PACKAGE_PATH=/abs/path/to/the.zip
  lambda_package_path = get_env("LAMBDA_PACKAGE_PATH")

  halo_base_url = "https://ec1helpdesk.haloitsm.com"

  # Adopted live stack (state key csd/m2c-alert-integration/terraform.tfstate):
  # existing names are kept so nothing is replaced.
  lambda_function_name = "csd-m2c-non-prod-alert-processor"
  lambda_role_name     = "csd-m2c-non-prod-alert-processor-role"
  lambda_policy_name   = "csd-m2c-non-prod-alert-processor-policy"
  dynamodb_table_name  = "csd-m2c-non-prod-alert-dedup"
  api_name             = "csd-m2c-non-prod-alerts-api"

  tags = local.tags
}
