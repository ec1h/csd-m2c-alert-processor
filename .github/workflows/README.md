# Workflows

All workflows are repo-owned (snake_case names, actions pinned by SHA, no `ec1h/reusable-workflows` calls). They are written so they can be lifted into a `workflow_call` reusable workflow later.

| File | Trigger | What it does |
|---|---|---|
| `build.yml` | push / PR / manual | Runs tests, gitleaks secret scan, then packages the Lambda zip (`csd-m2c-alert-processor-<sha>.zip` + `.sha256`) as an artifact. |
| `create_release.yml` | manual (`scope`: PATCH/MINOR/MAJOR), default branch only | Takes the zip the successful Build produced for that exact commit, verifies its hash, and publishes a semver GitHub Release with the zip attached. Never rebuilds. |
| `deploy.yml` | manual (`environment`, `release_tag`, `apply`, `allow_destroy`) | Downloads the release zip, verifies the hash, authenticates to AWS with OIDC, runs `terragrunt plan`, blocks any destroy/replace unless `allow_destroy`, and applies the saved plan only when `apply` is true. Rollback = deploy an older tag. |
| `live_halo_smoke.yml` | manual | Runs `tests/test_halo_live_integration.py` against a real Halo instance (auth-only unless `allow_ticket_creation`). Uses the `uat` environment's Halo secrets. |

## Release and deploy flow

1. Merge to `main` -> `build.yml` produces the tested zip.
2. Run `create_release.yml` -> tag `vX.Y.Z` with the zip attached.
3. Run `deploy.yml` with `environment=test`, the tag, `apply=false` -> read the plan.
4. Re-run with `apply=true` -> approval gate (GitHub Environment reviewers) -> apply.
5. Promote the same tag to `qa`, then `uat`. Never rebuild between environments.

## One-time setup (not done by these files)

- **GitHub Environments** `test`, `qa`, `uat` (repo Settings -> Environments) with required reviewers. `deploy.yml` runs in the chosen environment, so this is the approval gate.
- **AWS OIDC deploy role.** `.github/environments/.env.<environment>` (`CSD_AWS_ACCOUNT_ID`, `CSD_STAGE`, `ROLE_NAME`) selects the role. `ROLE_NAME` currently points at `github-devops-provisioner` (Administrator, trusts `repo:ec1h/*:*`). Replace it with a dedicated least-privilege role trusted only for `repo:ec1h/csd-m2c-alert-processor:environment:<env>`; the IAM owner creates it.
- **Lambda credentials** (`HALO_*`, `WEBHOOK_SECRET`) are set on the function out-of-band; Terraform ignores `environment` changes.

## Environments

`test`, `qa`, `uat` deploy into the same non-prod AWS account (905418043725) under `iac/non-prod/<environment>/alert-processor`. `test` adopts the live stack (live names, existing state bucket and key, `moved` blocks); `qa`/`uat` would be new stacks.

`prod` is scaffolded but not dispatchable: `.github/environments/.env.prod` and `iac/prod/account.hcl` carry the placeholder account `000000000000` on purpose. See `iac/prod/prod/alert-processor/README.md`.
