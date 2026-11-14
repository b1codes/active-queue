output "cloud_run_url" {
  description = "URL of the Prod Cloud Run service"
  value       = module.prod_app.cloud_run_url
}

output "cloud_run_service_name" {
  description = "Name of the Prod Cloud Run service"
  value       = module.prod_app.cloud_run_service_name
}

output "artifact_registry_repository_id" {
  description = "Artifact Registry repository for Prod API images"
  value       = module.prod_app.artifact_registry_repository_id
}

output "smoke_test_service_account_email" {
  description = "Service account that signs the Prod smoke test's custom token"
  value       = module.prod_app.smoke_test_service_account_email
}
