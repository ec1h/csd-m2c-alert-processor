# Project Guidelines

## Architecture
AWS Lambda (`src/handlers/alert-processor/`) triggered by a Grafana Alertmanager webhook; creates/updates Halo ITSM tickets; dedups via DynamoDB. See [README.md](../README.md) for the full request/response contract. IaC lives in `iac/` (Terragrunt callers under `iac/non-prod/{test,qa,uat}/` and `iac/prod/prod/`, reusable module in `iac/modules/alert-processor/`). This repo is the only Python codebase in the `ec1h` org, so there is no upstream Python reusable CI workflow yet - see `.github/workflows/reusable_build_and_test_python_service.yml`, a local reference design pending upstream to `ec1h/reusable-workflows`.

## Build and Test
- `pip install -r requirements-dev.txt && pytest -q` - full suite.
- Lambda packaging happens once, in `build.yml`; `create_release.yml` attaches that exact zip to a release and Terraform deploys it via `lambda_package_path` - never hand-build or upload a zip separately.

## Conventions
- Environments: `test`/`qa`/`uat` share one known non-prod AWS account; `prod` is scaffolded but intentionally non-appliable (placeholder `000000000000` account ID) until a real prod account exists - never replace that placeholder with a guessed value.
- `.github/environments/.env.<environment>` (committed, non-secret) is read internally by `ec1h/reusable-workflows`'s terragrunt plan/apply workflows to resolve the target AWS account/role - every environment needs one before it can deploy.
- `terragrunt-apply.yml` uses a `type: environment` dispatch dropdown, never a hardcoded environment value - matches the org's Node/Java repo conventions.
- Follow the `devops-mindset` skill for any infra/pipeline/packaging/promotion task in this repo.
