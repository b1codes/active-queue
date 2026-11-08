# tflint config for every Terraform root and module (ci.yml `terraform` job).
plugin "terraform" {
  enabled = true
  preset  = "all"
}

plugin "google" {
  enabled = true
  version = "0.38.0"
  source  = "github.com/terraform-linters/tflint-ruleset-google"
}
