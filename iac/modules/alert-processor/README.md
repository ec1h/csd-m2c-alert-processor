# alert-processor (Terraform module)

Defines the Lambda, least-privilege IAM, DynamoDB dedup table, HTTP API Gateway route (`POST /m2c-alerts`), CloudWatch log groups, and CloudWatch alarms (Lambda errors, Halo request failures, unmapped alert types).

Reads Halo/webhook credentials from a pre-existing Secrets Manager secret (`var.halo_secret_name`) - this module never creates or writes the secret value.

No Lambda DLQ/failure-destination is defined: API Gateway invokes the Lambda synchronously, and destinations/DLQs only apply to asynchronous invocations, so one here would never fire. Failure visibility comes from the handler's non-2xx response contract and the CloudWatch alarms above.
