# alert-processor (Terraform module)

Defines the Lambda, least-privilege IAM, DynamoDB dedup table, HTTP API Gateway route (`POST /m2c-alerts`), CloudWatch log groups, and CloudWatch alarms (Lambda errors, Halo request failures, unmapped alert types).

The Lambda's credentials (`HALO_CLIENT_ID`, `HALO_CLIENT_SECRET`, `WEBHOOK_SECRET`) are not managed here: the function's `environment` block is in `ignore_changes`, so values set on the live function stay untouched and never pass through Terraform. Moving them to Secrets Manager is a follow-up.

The code comes from `var.lambda_package_path`, the release zip built by `build.yml`; Terraform never builds code. Adopted stacks pass the `*_name` overrides so existing resources keep their names; `moved` blocks in `main.tf` map the legacy state addresses onto this module.

No Lambda DLQ/failure-destination is defined: API Gateway invokes the Lambda synchronously, and destinations/DLQs only apply to asynchronous invocations, so one here would never fire. Failure visibility comes from the handler's non-2xx response contract and the CloudWatch alarms above.
