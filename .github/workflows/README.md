# Workflows

- `tests.yml` - pytest, on push/PR.
- `terraform-checks.yml` - `terraform fmt -check` + `validate` (backend=false, no AWS contact), on PR.
- `security.yml` - gitleaks secret scan, on push/PR.
- `terragrunt-plan.yml` - calls the org's `reusable_terragrunt_plan.yml` for UAT, on PR. Plan only, never applies.
- `terragrunt-apply.yml` - `workflow_dispatch` only, gated by a GitHub Environment (`uat`) that must have required reviewers configured in repo settings (not done by this file). Never runs on push or PR.

**Open item:** the exact `with:` input names and current version tag for `ec1h/reusable-workflows` were inferred from other repos' callers - the reusable-workflows repo itself could not be inspected in this session. Confirm both before merging `terragrunt-plan.yml`/`terragrunt-apply.yml`.
