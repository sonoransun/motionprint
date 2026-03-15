output "cloud_run_uri" {
  value = google_cloud_run_v2_service.main.uri
}

output "neg_id" {
  value = google_compute_region_network_endpoint_group.main.id
}

output "artifact_registry_url" {
  value = "${var.gcp_region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}
