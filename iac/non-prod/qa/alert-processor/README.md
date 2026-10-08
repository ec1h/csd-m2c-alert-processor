# qa alert-processor (Terragrunt caller)

Calls `iac/modules/alert-processor` with qa-specific inputs, in the same non-prod AWS account (905418043725) as uat/test.

`halo_secret_name` (`qa/csd-m2c-alert-processor/halo`) must exist in Secrets Manager (JSON keys `HALO_CLIENT_ID`, `HALO_CLIENT_SECRET`, `WEBHOOK_SECRET`) before the first apply - this module only reads it, it does not create it.
