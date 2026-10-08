# Read-only visualization surface for IT Operations and the upstream IoT
# team. Who can view it (console IAM/SSO, cross-account share, or a
# scheduled export) is a separate, not-yet-decided access-control question.
resource "aws_cloudwatch_dashboard" "alert_processor" {
  dashboard_name = local.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Ticket outcomes"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 300
          metrics = [
            ["M2CAlertProcessor", "TicketCreated"],
            ["M2CAlertProcessor", "TicketUpdated"],
            ["M2CAlertProcessor", "DuplicateSkipped"],
          ]
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Failures needing attention"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 300
          metrics = [
            ["M2CAlertProcessor", "HaloRequestFailure"],
            ["M2CAlertProcessor", "UnmappedAlertType"],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.this.function_name],
          ]
        }
      },
      {
        type   = "log"
        width  = 24
        height = 6
        properties = {
          title  = "Recent errors and unmapped alert types"
          region = var.aws_region
          view   = "table"
          query  = "SOURCE '${aws_cloudwatch_log_group.lambda.name}' | fields @timestamp, @message | filter @message like /\\[ERROR\\]/ or @message like /\\[UNMAPPED\\]/ | sort @timestamp desc | limit 50"
        }
      },
    ]
  })
}
