module "gcp_us_central1" {
  source = "../../modules/gcp-region"

  project_id      = var.gcp_project_id
  gcp_region      = "us-central1"
  container_image = "${module.gcp_us_central1.artifact_registry_url}/motionprint-service:${var.image_tag}"

  min_instances          = 1
  max_instances          = 20
  max_concurrent_renders = 4
}

module "gcp_europe_west1" {
  source = "../../modules/gcp-region"

  project_id      = var.gcp_project_id
  gcp_region      = "europe-west1"
  container_image = "${module.gcp_europe_west1.artifact_registry_url}/motionprint-service:${var.image_tag}"

  min_instances          = 1
  max_instances          = 20
  max_concurrent_renders = 4
}

# --- Global HTTP(S) Load Balancer ---

resource "google_compute_backend_service" "main" {
  name                  = "motionprint-production-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 60

  backend {
    group = module.gcp_us_central1.neg_id
  }

  backend {
    group = module.gcp_europe_west1.neg_id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_url_map" "main" {
  name            = "motionprint-production-urlmap"
  default_service = google_compute_backend_service.main.id
}

resource "google_compute_managed_ssl_certificate" "main" {
  name = "motionprint-production-cert"

  managed {
    domains = ["gcp.${var.domain_name}"]
  }
}

resource "google_compute_target_https_proxy" "main" {
  name             = "motionprint-production-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_forwarding_rule" "main" {
  name                  = "motionprint-production-forwarding"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_https_proxy.main.id
  port_range            = "443"
  ip_protocol           = "TCP"
}

# --- HTTP → HTTPS Redirect ---

resource "google_compute_url_map" "http_redirect" {
  name = "motionprint-production-http-redirect"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  name    = "motionprint-production-http-proxy"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  name                  = "motionprint-production-http-redirect"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_http_proxy.redirect.id
  port_range            = "80"
  ip_protocol           = "TCP"
}
