resource "google_compute_region_network_endpoint_group" "main" {
  name                  = "${local.service_name}-neg"
  region                = var.gcp_region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.main.name
  }
}
