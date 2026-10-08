# BLOCKED: real prod AWS account ID not yet known (confirmed with repo owner
# 2026-10-06 - this service has only ever run in the non-prod account).
# "000000000000" is AWS's own placeholder/example account ID - it is not a
# real, assumable account, so a stray `terragrunt apply` here fails on STS
# auth instead of silently landing in the wrong place. Replace with the real
# value (and fill in `.github/environments/.env.prod`) once the prod account
# exists, before ever running apply against this folder.
locals {
  aws_account_id = "000000000000"
  account_name   = "prod"
}
