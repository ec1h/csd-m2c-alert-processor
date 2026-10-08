# UAT alert-processor (Terragrunt caller)

Calls `iac/modules/alert-processor` with UAT-specific inputs. No production caller exists yet.

`halo_secret_name` must already exist in Secrets Manager (JSON keys `HALO_CLIENT_ID`, `HALO_CLIENT_SECRET`, `WEBHOOK_SECRET`) before the first apply - this module only reads it.

Resource names are derived from `project_name`/`component_name`/`environment` and will **not** match the currently-deployed Lambda/table/API Gateway names. Applying this as-is creates new, parallel resources; adopting the existing ones requires either a deliberate `terraform import` (matching names first) or a planned cutover - do not assume this replaces the live resources.
