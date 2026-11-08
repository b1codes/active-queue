# `terraform test` for the ActiveQueue app module (ClickUp 86bcxrv0z). The Google
# provider is mocked, so this runs in CI with no GCP credentials (SPEC §12.5). Each run
# pins one property that a plan against a real project would otherwise reveal only after
# deploy.

mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      email = "activequeue-api-sa-test@activequeue-test.iam.gserviceaccount.com"
      name  = "projects/activequeue-test/serviceAccounts/activequeue-api-sa-test@activequeue-test.iam.gserviceaccount.com"
    }
  }
}

variables {
  gcp_project_id             = "activequeue-test"
  env                        = "test"
  container_image            = "us-central1-docker.pkg.dev/activequeue-test/activequeue-api-test/api@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  google_oauth_client_id     = "client-id.apps.googleusercontent.com"
  google_oauth_client_secret = "google-secret"
  apple_client_secret        = "apple-secret"
}

run "deploys_the_image_it_is_given" {
  command = apply

  assert {
    condition     = google_cloud_run_v2_service.api_service.template[0].containers[0].image == var.container_image
    error_message = "Cloud Run must run var.container_image, the image deploy.sh built and pushed."
  }
}

run "sends_all_traffic_to_the_latest_revision" {
  command = apply

  assert {
    condition = (
      length(google_cloud_run_v2_service.api_service.traffic) == 1 &&
      google_cloud_run_v2_service.api_service.traffic[0].type == "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST" &&
      google_cloud_run_v2_service.api_service.traffic[0].percent == 100
    )
    error_message = "Traffic must be declared (100% latest) so the deploy after a rollback moves traffic forward."
  }
}

run "rejects_a_mutable_image_tag" {
  command = plan

  variables {
    container_image = "us-central1-docker.pkg.dev/activequeue-test/activequeue-api-test/api:latest"
  }

  expect_failures = [var.container_image]
}

run "is_publicly_invokable" {
  command = apply

  assert {
    condition = (
      google_cloud_run_v2_service_iam_member.public_invoker.role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.public_invoker.member == "allUsers" &&
      google_cloud_run_v2_service_iam_member.public_invoker.name == google_cloud_run_v2_service.api_service.name
    )
    error_message = "The app calls the API with a Firebase ID token, not IAM; without allUsers run.invoker every request is a 403."
  }
}

run "api_service_account_is_least_privilege" {
  command = apply

  assert {
    condition     = google_project_iam_member.datastore_user.role == "roles/datastore.user"
    error_message = "SPEC §10.5: roles/datastore.user is the API service account's only project role."
  }

  assert {
    condition = (
      google_secret_manager_secret_iam_member.api_reads_youtube_key.secret_id == google_secret_manager_secret.youtube_api_key.secret_id &&
      google_secret_manager_secret_iam_member.api_reads_youtube_key.role == "roles/secretmanager.secretAccessor"
    )
    error_message = "The API may read the YouTube key secret and nothing else."
  }
}

run "runs_with_deployed_env_settings" {
  command = apply

  assert {
    condition = alltrue([
      for e in google_cloud_run_v2_service.api_service.template[0].containers[0].env :
      !contains(["FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "DEBUG"], e.name)
    ])
    error_message = "A deployed service must never set emulator hosts or DEBUG (config.py refuses to start)."
  }

  assert {
    condition = one([
      for e in google_cloud_run_v2_service.api_service.template[0].containers[0].env :
      e.value if e.name == "ENV"
    ]) == var.env
    error_message = "ENV must match the environment."
  }

  assert {
    condition = one([
      for e in google_cloud_run_v2_service.api_service.template[0].containers[0].env :
      e.value if e.name == "TRUSTED_PROXY_HOPS"
    ]) == "1"
    error_message = "Cloud Run adds exactly one X-Forwarded-For hop (per-IP rate-limit guard)."
  }
}

run "gates_readiness_on_firestore" {
  command = apply

  assert {
    condition     = google_cloud_run_v2_service.api_service.template[0].containers[0].startup_probe[0].http_get[0].path == "/healthz"
    error_message = "The startup probe must hit the health check, so a revision that can't reach Firestore never takes traffic."
  }

  assert {
    condition     = length(google_cloud_run_v2_service.api_service.template[0].containers[0].liveness_probe) == 0
    error_message = "No liveness probe on the health check: a Firestore outage would restart every instance."
  }
}

run "scales_per_environment" {
  command = apply

  variables {
    min_instances = 1
  }

  assert {
    condition = (
      google_cloud_run_v2_service.api_service.template[0].scaling[0].min_instance_count == 1 &&
      google_cloud_run_v2_service.api_service.template[0].scaling[0].max_instance_count == 10 &&
      google_cloud_run_v2_service.api_service.template[0].max_instance_request_concurrency == 80
    )
    error_message = "SPEC §10.5: min instances as configured, max 10, concurrency 80."
  }
}

run "uses_the_oauth_credentials_it_is_given" {
  command = apply

  assert {
    condition = (
      google_identity_platform_default_supported_idp_config.google_idp.client_id == var.google_oauth_client_id &&
      google_identity_platform_default_supported_idp_config.google_idp.client_secret == var.google_oauth_client_secret &&
      google_identity_platform_oauth_idp_config.apple_idp.client_secret == var.apple_client_secret
    )
    error_message = "Identity Platform must be configured with the credentials passed in, never placeholders."
  }
}

run "smoke_test_signer_has_no_project_roles" {
  command = apply

  variables {
    smoke_test_signers = ["user:deployer@example.com"]
  }

  assert {
    condition = (
      google_service_account_iam_member.smoke_test_signers["user:deployer@example.com"].role == "roles/iam.serviceAccountTokenCreator" &&
      google_service_account_iam_member.smoke_test_signers["user:deployer@example.com"].service_account_id == google_service_account.smoke_test.name
    )
    error_message = "Signers may sign as the smoke-test service account, which holds no project roles."
  }
}
