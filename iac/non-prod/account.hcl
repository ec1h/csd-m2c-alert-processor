# Confirmed from this Lambda's deployed ARN in config-audit.json
# (arn:aws:lambda:af-south-1:905418043725:function:...) and corroborated by
# the sibling `ec1h-go-n-pay-admin-portal` repo's iac/non-prod/account.hcl,
# which targets the same account.
locals {
  aws_account_id = "905418043725"
  account_name   = "non-prod"
}
