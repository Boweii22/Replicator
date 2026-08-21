param(
  [string]$ProjectId = $env:GOOGLE_CLOUD_PROJECT,
  [string]$Region = $(if ($env:GOOGLE_CLOUD_LOCATION) { $env:GOOGLE_CLOUD_LOCATION } else { "europe-west1" })
)

$ErrorActionPreference = "Stop"
if (-not $ProjectId) { throw "Pass -ProjectId or set GOOGLE_CLOUD_PROJECT." }

function Invoke-Checked {
  param([string]$Command, [string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

$Gcloud = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$Terraform = if (Test-Path ".tools-terraform\terraform.exe") {
  (Resolve-Path ".tools-terraform\terraform.exe").Path
} else {
  (Get-Command terraform -ErrorAction Stop).Source
}
$Tag = (git rev-parse --short HEAD).Trim()
$Image = "$Region-docker.pkg.dev/$ProjectId/replicator/app:$Tag"

Invoke-Checked $Gcloud @("config", "set", "project", $ProjectId)
Invoke-Checked $Gcloud @("services", "enable", "cloudbuild.googleapis.com",
  "artifactregistry.googleapis.com", "run.googleapis.com")
Invoke-Checked $Terraform @("-chdir=infra", "init", "-input=false")
Invoke-Checked $Terraform @("-chdir=infra", "apply", "-auto-approve",
  "-target=google_project_service.apis",
  "-target=google_artifact_registry_repository.images",
  "-var=project_id=$ProjectId", "-var=region=$Region", "-var=image=$Image")
Invoke-Checked $Gcloud @("builds", "submit", "--region=$Region", "--config=cloudbuild.yaml",
  "--substitutions=_IMAGE=$Image", ".")
Invoke-Checked $Terraform @("-chdir=infra", "apply", "-auto-approve",
  "-var=project_id=$ProjectId", "-var=region=$Region", "-var=image=$Image")

$ApiUrl = & $Terraform @("-chdir=infra", "output", "-raw", "api_url")
if ($LASTEXITCODE -ne 0) { throw "Terraform output failed with exit code $LASTEXITCODE" }
Write-Host "Deployment complete: $ApiUrl"
