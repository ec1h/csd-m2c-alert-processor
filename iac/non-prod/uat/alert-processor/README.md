# UAT alert-processor (Terragrunt caller)

Calls `iac/modules/alert-processor` with UAT-specific inputs. No production caller exists yet.

Not yet deployed. Set `LAMBDA_PACKAGE_PATH` to the release zip. Credentials are not managed by Terraform (the function's `environment` is ignored), so they must be set on the function out-of-band after creation.

Names derive from `project_name`/`component_name`/`environment`, so this creates a new stack separate from the live `test` stack.
