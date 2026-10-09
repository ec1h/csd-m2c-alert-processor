# prod alert-processor (Terragrunt caller) - NOT YET APPLIABLE

Calls `iac/modules/alert-processor` with prod-specific inputs. **Blocked**: there is no real prod AWS account yet - this service has only ever run in the non-prod account (905418043725). `iac/prod/account.hcl` has a deliberately invalid placeholder account ID (`000000000000`) so an accidental apply fails on STS auth rather than landing somewhere unexpected.

Before this folder is usable:
1. Get the real prod AWS account ID and replace it in `iac/prod/account.hcl`.
2. Confirm the `prod/csd-m2c-alert-processor/halo` Secrets Manager secret exists in that account (JSON keys `HALO_CLIENT_ID`, `HALO_CLIENT_SECRET`, `WEBHOOK_SECRET`) - this module only reads it, it does not create it.
3. Fill in the real account ID in `.github/environments/.env.prod`.
4. Create a `prod` GitHub Environment (repo Settings) with required reviewers before anyone can dispatch `deploy.yml` against it.
