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
  component_name    = "alert-processor"
  lambda_source_dir = "${get_repo_root()}/src"

  halo_base_url    = "https://ec1helpdesk.haloitsm.com"
  halo_secret_name = "uat/csd-m2c-alert-processor/halo"

  tags = local.tags
}
