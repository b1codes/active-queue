output "cloud_run_url" {
  description = "URL of the Dev Cloud Run service"
  value       = module.dev_app.cloud_run_url
}

output "cloud_run_service_name" {
  description = "Name of the Dev Cloud Run service"
  value       = module.dev_app.cloud_run_service_name
}

output "artifact_registry_repository_id" {
  description = "Artifact Registry repository for Dev API images"
  value       = module.dev_app.artifact_registry_repository_id
}

output "smoke_test_service_account_email" {
  description = "Service account that signs the Dev smoke test's custom token"
  value       = module.dev_app.smoke_test_service_account_email
}
