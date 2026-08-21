output "artifact_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "worker_urls" {
  value = { for k, v in google_cloud_run_v2_service.worker : k => v.uri }
}

output "topics" {
  value = sort(tolist(local.all_topics))
}
