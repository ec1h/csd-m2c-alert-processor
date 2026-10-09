# qa alert-processor (Terragrunt caller)

Calls `iac/modules/alert-processor` with qa-specific inputs, in the same non-prod AWS account (905418043725) as uat/test.

Not yet deployed. Set `LAMBDA_PACKAGE_PATH` to the release zip. Credentials are not managed by Terraform (the function's `environment` is ignored), so they must be set on the function out-of-band after creation.
