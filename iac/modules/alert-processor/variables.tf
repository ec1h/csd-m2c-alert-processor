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

variable "lambda_source_dir" {
  type        = string
  description = "Absolute path to the Lambda source directory (this repo's src/handlers/alert-processor folder). Use get_repo_root() in Terragrunt."
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

variable "halo_secret_name" {
  type        = string
  description = "Name of a pre-existing Secrets Manager secret holding HALO_CLIENT_ID, HALO_CLIENT_SECRET, WEBHOOK_SECRET as JSON keys. Not created by this module - populate it out-of-band before first apply."
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
  type    = number
  default = 10
}
