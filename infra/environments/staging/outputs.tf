output "cloud_run_url" {
  description = "URL of the Staging Cloud Run service"
  value       = module.staging_app.cloud_run_url
}

output "cloud_run_service_name" {
  description = "Name of the Staging Cloud Run service"
  value       = module.staging_app.cloud_run_service_name
}

output "artifact_registry_repository_id" {
  description = "Artifact Registry repository for Staging API images"
  value       = module.staging_app.artifact_registry_repository_id
}

output "smoke_test_service_account_email" {
  description = "Service account that signs the Staging smoke test's custom token"
  value       = module.staging_app.smoke_test_service_account_email
}
