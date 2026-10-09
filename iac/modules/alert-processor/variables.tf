variable "project_name" {
  type = string
}

variable "component_name" {
  type    = string
  default = "alert-processor"
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "default_tags" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "lambda_package_path" {
  type        = string
  description = "Path to the release zip built by build.yml (csd-m2c-alert-processor-<sha>.zip). Terraform deploys this exact file and never builds code itself."
}

variable "lambda_function_name" {
  type        = string
  default     = null
  description = "Override the Lambda name. Set when adopting an existing function so it is not replaced."
}

variable "lambda_role_name" {
  type        = string
  default     = null
  description = "Override the Lambda execution role name (adoption)."
}

variable "lambda_policy_name" {
  type        = string
  default     = null
  description = "Override the Lambda permissions policy name (adoption)."
}

variable "dynamodb_table_name" {
  type        = string
  default     = null
  description = "Override the dedup table name (adoption). Changing it replaces the table."
}

variable "api_name" {
  type        = string
  default     = null
  description = "Override the HTTP API name (adoption)."
}

variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}

variable "lambda_memory_size" {
  type    = number
  default = 128
}

variable "lambda_timeout" {
  type    = number
  default = 30
}

variable "lambda_log_retention_days" {
  type    = number
  default = 30
}

variable "dynamodb_ttl_days" {
  type    = number
  default = 90
}

variable "halo_base_url" {
  type        = string
  description = "Halo ITSM base URL, e.g. https://ec1helpdesk.haloitsm.com"
}

variable "halo_ticket_type_id" {
  type    = number
  default = 64
}

variable "halo_team_ec1" {
  type    = number
  default = 12
}

variable "halo_team_jw" {
  type    = number
  default = 13
}

variable "halo_team_internal" {
  type    = number
  default = 14
}

variable "alarm_actions" {
  type        = list(string)
  default     = []
  description = "Additional SNS topic ARNs to notify on alarm, alongside this module's own topic."
}

variable "api_gateway_throttling_burst_limit" {
  type    = number
  default = 20
}

variable "api_gateway_throttling_rate_limit" {
  type        = number
  default     = null
  description = "Null leaves the stage unthrottled (current live behaviour)."
}
