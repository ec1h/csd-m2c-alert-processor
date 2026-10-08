# No subscriptions attached here deliberately - wire real notification
# targets (email/Slack/etc.) manually or via var.alarm_actions after review.
resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = concat([aws_sns_topic.alarms.arn], var.alarm_actions)
  tags          = local.tags
}

# Emitted by src/handlers/alert-processor/metrics.py when a Halo API call fails (see lambda_function.py).
resource "aws_cloudwatch_metric_alarm" "halo_request_failures" {
  alarm_name          = "${local.name}-halo-request-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HaloRequestFailure"
  namespace           = "M2CAlertProcessor"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  alarm_actions = concat([aws_sns_topic.alarms.arn], var.alarm_actions)
  tags          = local.tags
}

# Emitted for any Grafana M2C label the routing table doesn't recognize
# (e.g. "Boot") - see src/handlers/alert-processor/routing.py. No ticket is created for these.
resource "aws_cloudwatch_metric_alarm" "unmapped_alert_types" {
  alarm_name          = "${local.name}-unmapped-alert-types"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "UnmappedAlertType"
  namespace           = "M2CAlertProcessor"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  alarm_actions = concat([aws_sns_topic.alarms.arn], var.alarm_actions)
  tags          = local.tags
}
