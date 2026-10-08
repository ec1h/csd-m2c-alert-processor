# Workflows

- `tests.yml` - calls `reusable_build_and_test_python_service.yml`, on push/PR.
- `reusable_build_and_test_python_service.yml` - local reference design for an org-wide Python build/test reusable workflow, mirroring `ec1h/reusable-workflows`' `reusable_build_and_test_node_service.yml` shape (pip install + pytest). This repo is the only Python codebase in the org, so there is no upstream Python equivalent yet - propose moving this file into `ec1h/reusable-workflows` once reviewed, so future Python repos can call it the same way Node repos call theirs.
- `terraform-checks.yml` - `terraform fmt -check` + `validate` (backend=false, no AWS contact), on PR.
- `security.yml` - gitleaks secret scan (self-hosted CLI, not gitleaks-action - avoids the org's missing GITLEAKS_LICENSE), on push/PR.
- `terragrunt-plan.yml` - calls the org's `reusable_terragrunt_plan.yml` in a matrix over `test`/`qa`/`uat` (same non-prod account), on PR. `prod` is deliberately excluded - see below. Plan only, never applies.
- `terragrunt-apply.yml` - `workflow_dispatch` with an `environment` dropdown (`type: environment`, defaults to `uat`), matching the pattern used by `ec1h-go-n-pay-admin-portal`/`ec1h-go-n-pay-payment-gateway-utils`. Gated by a GitHub Environment matching the chosen input, which must have required reviewers configured in repo settings (not done by this file). Never runs on push or PR.
- `live-halo-smoke.yml` - `workflow_dispatch` only, gated by the same `uat` Environment. Runs `tests/test_halo_live_integration.py` against a real Halo instance once access is granted - auth-only by default, opt in to real ticket creation via the `allow_ticket_creation` input. Requires `HALO_LIVE_BASE_URL`/`HALO_LIVE_CLIENT_ID`/`HALO_LIVE_CLIENT_SECRET` (and optionally `HALO_LIVE_TICKET_TYPE_ID`/`HALO_LIVE_TEAM_ID`) configured on the `uat` environment.

## `.github/environments/.env.<environment>`

Mirrors the convention found in `ec1h-go-n-pay-admin-portal` and `ec1h-go-n-pay-payment-gateway-utils`: a committed, non-secret dotenv file per environment (`CSD_AWS_ACCOUNT_ID`, `CSD_STAGE`, `ROLE_NAME`) that the org's `reusable_terragrunt_plan.yml`/`reusable_terragrunt_apply.yml` read internally to resolve the target AWS account/role. This repo previously had none - `.env.uat` was added with `CSD_AWS_ACCOUNT_ID=905418043725` (verified against this repo's own `account.hcl` and `config-audit.json`) and `CSD_STAGE=non-prod`. `ROLE_NAME=github-devops-provisioner` was copied from both sibling repos but is unverified for this repo's IAM trust policy - confirm with whoever administers the AWS OIDC role before relying on it.

**Open item:** the exact `with:` input names and current version tag for `ec1h/reusable-workflows` were inferred from other repos' callers - the reusable-workflows repo itself returns 404 to this session's GitHub access (likely a scoping gap in that integration, not proof the repo is missing - three other repos call it successfully). Confirm both before merging `terragrunt-plan.yml`/`terragrunt-apply.yml`.

## Environment lineup

`test`, `qa`, `uat` all deploy into the same, known non-prod AWS account (905418043725) under `iac/non-prod/<environment>/alert-processor` - each needs its own pre-existing Secrets Manager secret (`<environment>/csd-m2c-alert-processor/halo`) before a first apply.

`prod` is **scaffolded but not yet usable**: there is no real prod AWS account for this service yet (confirmed with the repo owner 2026-10-06 - it has only ever run in non-prod). `iac/prod/account.hcl` and `.github/environments/.env.prod` both carry the deliberately invalid placeholder account ID `000000000000` so a stray apply fails on STS auth instead of landing somewhere unexpected. See `iac/prod/prod/alert-processor/README.md` for what has to happen before `prod` becomes dispatchable (real account ID, confirmed secret, GitHub Environment with required reviewers).
