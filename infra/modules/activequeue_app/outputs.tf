output "cloud_run_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.api_service.uri
}

output "service_account_email" {
  description = "Email of the API service account"
  value       = google_service_account.api_sa.email
}

output "artifact_registry_repository_id" {
  description = "ID of the Artifact Registry repository"
  value       = google_artifact_registry_repository.api_repo.repository_id
}
