locals {
  services = toset([
    "aiplatform.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com",
    "firestore.googleapis.com", "logging.googleapis.com", "pubsub.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com", "secretmanager.googleapis.com", "storage.googleapis.com",
    "cloudtrace.googleapis.com", "cloudscheduler.googleapis.com",
  ])
  worker_topics = {
    reader   = "replication.requested"
    planner  = "plan.ready"
    executor = "job.dispatch"
    verifier = "verify.requested"
    reporter = "report.ready"
  }
  all_topics = toset(concat(values(local.worker_topics), ["job.finished", "dead-letter"]))
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each           = local.services
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "replicator"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-replicator-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning { enabled = true }
  lifecycle_rule {
    condition {
      age                = 30
      num_newer_versions = 2
    }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.apis]
}

resource "google_firestore_database" "state" {
  name        = "replicator"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

resource "google_pubsub_topic" "topics" {
  for_each   = local.all_topics
  name       = each.value
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id   = "replicator-runtime"
  display_name = "Replicator services"
}

resource "google_service_account" "push" {
  account_id   = "replicator-pubsub-push"
  display_name = "Authenticated Pub/Sub delivery"
}

resource "google_service_account" "runner" {
  account_id   = "replicator-runner"
  display_name = "Restricted experiment runner"
}

resource "google_service_account" "builder" {
  account_id   = "replicator-builder"
  display_name = "Restricted experiment image builder"
}

resource "google_cloud_run_v2_service" "worker" {
  for_each = local.worker_topics
  name     = "replicator-${each.key}"
  location = var.region
  ingress  = var.allowed_ingress
  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = var.image
      env {
        name  = "SERVICE_NAME"
        value = each.key
      }
      env {
        name  = "APP_MODULE"
        value = "services.worker_main:app"
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.state.name
      }
      env {
        name  = "MODEL_ID"
        value = var.model_id
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "ARTIFACT_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
      env {
        name  = "BUILD_SERVICE_ACCOUNT"
        value = google_service_account.builder.email
      }
      env {
        name  = "RUNNER_SERVICE_ACCOUNT"
        value = google_service_account.runner.email
      }
      env {
        name  = "RUNTIME_SERVICE_ACCOUNT"
        value = google_service_account.runtime.email
      }
      resources { limits = { cpu = "1", memory = "1Gi" } }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "api" {
  name     = "replicator-api"
  location = var.region
  ingress  = var.allowed_ingress
  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = var.image
      env {
        name  = "APP_MODULE"
        value = "services.api.main:app"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.state.name
      }
      env {
        name  = "ARTIFACT_BUCKET"
        value = google_storage_bucket.artifacts.name
      }
      resources { limits = { cpu = "1", memory = "1Gi" } }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "public_api" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "push_invoker" {
  for_each = local.worker_topics
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.worker[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.push.email}"
}

resource "google_pubsub_subscription" "worker" {
  for_each             = local.worker_topics
  name                 = "${each.value}-${each.key}"
  topic                = google_pubsub_topic.topics[each.value].id
  ack_deadline_seconds = 600
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker[each.key].uri}/pubsub"
    oidc_token {
      service_account_email = google_service_account.push.email
      audience              = google_cloud_run_v2_service.worker[each.key].uri
    }
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.topics["dead-letter"].id
    max_delivery_attempts = 5
  }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }
  depends_on = [google_cloud_run_v2_service_iam_member.push_invoker]
}

resource "google_pubsub_subscription" "job_finished_executor" {
  name                 = "job.finished-executor"
  topic                = google_pubsub_topic.topics["job.finished"].id
  ack_deadline_seconds = 600
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker["executor"].uri}/pubsub"
    oidc_token {
      service_account_email = google_service_account.push.email
      audience              = google_cloud_run_v2_service.worker["executor"].uri
    }
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.topics["dead-letter"].id
    max_delivery_attempts = 5
  }
  depends_on = [google_cloud_run_v2_service_iam_member.push_invoker]
}

resource "google_pubsub_topic_iam_member" "dead_letter_publish" {
  topic  = google_pubsub_topic.topics["dead-letter"].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dead_letter_forward" {
  for_each     = local.worker_topics
  subscription = google_pubsub_subscription.worker[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "job_finished_dead_letter_forward" {
  subscription = google_pubsub_subscription.job_finished_executor.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_job" "janitor" {
  name     = "replicator-janitor"
  location = var.region
  template {
    task_count = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "300s"
      max_retries     = 1
      containers {
        image   = var.image
        command = ["python", "-m", "services.janitor.main"]
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "FIRESTORE_DATABASE"
          value = google_firestore_database.state.name
        }
      }
    }
  }
}

resource "google_service_account" "scheduler" {
  account_id   = "replicator-scheduler"
  display_name = "Replicator janitor scheduler"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_janitor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.janitor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "janitor" {
  name      = "replicator-janitor"
  region    = var.region
  schedule  = "*/15 * * * *"
  time_zone = "Etc/UTC"
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.janitor.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_runs_janitor]
}

resource "google_secret_manager_secret" "github_token" {
  secret_id = "replicator-github-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "hf_token" {
  secret_id = "replicator-hf-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "runtime_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_publish" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_build" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_jobs" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_service_account_iam_member" "runtime_uses_runner" {
  service_account_id = google_service_account.runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_service_account_iam_member" "runtime_uses_builder" {
  service_account_id = google_service_account.builder.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_service_account_iam_member" "runtime_signs_reports" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "builder_push" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "builder_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_storage_bucket_iam_member" "builder_read_sources" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_storage_bucket_iam_member" "runtime_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# Runner access is intentionally object creation only. Per-replication prefix enforcement is
# added as an IAM Condition by the executor when it creates an ephemeral runner identity.
resource "google_storage_bucket_iam_member" "runner_create" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.runner.email}"
}
