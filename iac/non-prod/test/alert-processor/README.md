# test alert-processor (Terragrunt caller)

Calls `iac/modules/alert-processor` with test-specific inputs, in the same non-prod AWS account (905418043725) as uat/qa.

This caller **adopts the live non-prod stack**: it reuses the existing state (`s3://905418043725-terraform-af-south-1/csd/m2c-alert-integration/terraform.tfstate`) and the existing resource names, so the first plan must show no destroys or replacements. Credentials stay on the live Lambda and are not managed by Terraform.

Set `LAMBDA_PACKAGE_PATH` to the verified release zip before running Terragrunt.
