# Project Guidelines

## Architecture
AWS Lambda (`src/handlers/alert-processor/`) triggered by a Grafana Alertmanager webhook; creates/updates Halo ITSM tickets; dedups via DynamoDB. See [README.md](../README.md) for the full request/response contract. IaC lives in `iac/` (Terragrunt callers under `iac/non-prod/{test,qa,uat}/` and `iac/prod/prod/`, reusable module in `iac/modules/alert-processor/`). CI/CD is repo-owned (no reusable-workflow calls): `build.yml` (test, secret scan, package zip), `create_release.yml` (semver GitHub Release with the zip), `deploy.yml` (deploy a release tag with Terragrunt), `live_halo_smoke.yml`. They are structured so they can later be lifted into `ec1h/reusable-workflows`.

## Build and Test
- `pip install -r requirements-dev.txt && pytest -q` - full suite.
- Lambda packaging happens once, in `build.yml`; `create_release.yml` attaches that exact zip to a release and Terraform deploys it via `lambda_package_path` - never hand-build or upload a zip separately.

## Conventions
- Environments: `test`/`qa`/`uat` share one known non-prod AWS account; `prod` is scaffolded but intentionally non-appliable (placeholder `000000000000` account ID) until a real prod account exists - never replace that placeholder with a guessed value.
- `.github/environments/.env.<environment>` (committed, non-secret) is read by `deploy.yml` to resolve the target AWS account/role - every environment needs one before it can deploy.
- `deploy.yml` uses a `type: environment` dispatch dropdown, never a hardcoded environment value - matches the org's Node/Java repo conventions.
- Follow the `devops-mindset` skill for any infra/pipeline/packaging/promotion task in this repo.
