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
  component_name      = "alert-processor"
  lambda_package_path = get_env("LAMBDA_PACKAGE_PATH")

  halo_base_url = "https://ec1helpdesk.haloitsm.com"

  tags = local.tags
}
