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
$ProjectWorkspace = $ProjectId -replace '[^a-zA-Z0-9_-]', '-'
# Older deployments used Terraform's default workspace. Reuse it when it owns
# the API service instead of selecting a new workspace and trying to recreate
# live infrastructure that is absent from that new state.
Invoke-Checked $Terraform @("-chdir=infra", "workspace", "select", "default")
$DefaultResources = & $Terraform @("-chdir=infra", "state", "list")
if ($LASTEXITCODE -ne 0) { throw "Terraform state inspection failed with exit code $LASTEXITCODE" }
$Workspace = if ($DefaultResources -contains "google_cloud_run_v2_service.api") {
  "default"
} else {
  $ProjectWorkspace
}
if ($Workspace -ne "default") {
  & $Terraform @("-chdir=infra", "workspace", "select", $Workspace)
  if ($LASTEXITCODE -ne 0) {
    Invoke-Checked $Terraform @("-chdir=infra", "workspace", "new", $Workspace)
  }
}
Invoke-Checked $Terraform @("-chdir=infra", "apply", "-auto-approve",
  "-target=google_project_service.apis",
  "-target=google_artifact_registry_repository.images",
  "-target=google_service_account.builder",
  "-target=google_project_iam_member.builder_build",
  "-target=google_project_iam_member.builder_logs",
  "-target=google_project_iam_member.builder_source_read",
  "-target=google_artifact_registry_repository_iam_member.builder_push",
  "-var=project_id=$ProjectId", "-var=region=$Region", "-var=image=$Image")
Invoke-Checked $Gcloud @("builds", "submit", "--region=$Region", "--config=cloudbuild.yaml",
  "--service-account=projects/$ProjectId/serviceAccounts/replicator-builder@$ProjectId.iam.gserviceaccount.com",
  "--substitutions=_IMAGE=$Image", ".")
Invoke-Checked $Terraform @("-chdir=infra", "apply", "-auto-approve",
  "-target=google_cloud_run_v2_service.api",
  "-target=google_cloud_run_v2_service.worker",
  "-target=google_cloud_run_v2_job.janitor",
  "-var=project_id=$ProjectId", "-var=region=$Region", "-var=image=$Image")
Invoke-Checked $Terraform @("-chdir=infra", "apply", "-auto-approve",
  "-var=project_id=$ProjectId", "-var=region=$Region", "-var=image=$Image")

$ApiUrl = & $Terraform @("-chdir=infra", "output", "-raw", "api_url")
if ($LASTEXITCODE -ne 0) { throw "Terraform output failed with exit code $LASTEXITCODE" }
Write-Host "Deployment complete: $ApiUrl"
