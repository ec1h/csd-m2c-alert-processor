# Workflows

- `tests.yml` - pytest, on push/PR.
- `terraform-checks.yml` - `terraform fmt -check` + `validate` (backend=false, no AWS contact), on PR.
- `security.yml` - gitleaks secret scan, on push/PR.
- `terragrunt-plan.yml` - calls the org's `reusable_terragrunt_plan.yml` for UAT, on PR. Plan only, never applies.
- `terragrunt-apply.yml` - `workflow_dispatch` only, gated by a GitHub Environment (`uat`) that must have required reviewers configured in repo settings (not done by this file). Never runs on push or PR.
- `live-halo-smoke.yml` - `workflow_dispatch` only, gated by the same `uat` Environment. Runs `tests/test_halo_live_integration.py` against a real Halo instance once access is granted - auth-only by default, opt in to real ticket creation via the `allow_ticket_creation` input. Requires `HALO_LIVE_BASE_URL`/`HALO_LIVE_CLIENT_ID`/`HALO_LIVE_CLIENT_SECRET` (and optionally `HALO_LIVE_TICKET_TYPE_ID`/`HALO_LIVE_TEAM_ID`) configured on the `uat` environment.

**Open item:** the exact `with:` input names and current version tag for `ec1h/reusable-workflows` were inferred from other repos' callers - the reusable-workflows repo itself could not be inspected in this session. Confirm both before merging `terragrunt-plan.yml`/`terragrunt-apply.yml`.
