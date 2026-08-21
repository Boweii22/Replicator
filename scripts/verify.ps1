$ErrorActionPreference = "Stop"
python -m pytest -q -p no:cacheprovider
python -m compileall -q packages services runner
node --check apps/web/app.js
git diff --check

if (Get-Command terraform -ErrorAction SilentlyContinue) {
  terraform -chdir=infra fmt -check -recursive
  terraform -chdir=infra init -backend=false
  terraform -chdir=infra validate
} else {
  Write-Warning "Terraform is not installed; HCL validation was skipped."
}
