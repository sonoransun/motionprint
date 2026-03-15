locals {
  service_name = "${var.project_name}-${var.environment}"
}

resource "google_artifact_registry_repository" "main" {
  location      = var.gcp_region
  repository_id = local.service_name
  format        = "DOCKER"
  description   = "motionprint-service container images"
}

resource "google_cloud_run_v2_service" "main" {
  name     = local.service_name
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      ports {
        container_port = var.container_port
      }

      env {
        name  = "PORT"
        value = tostring(var.container_port)
      }
      env {
        name  = "MOTIONPRINT_CACHE_DIR"
        value = "/var/cache/motionprint"
      }
      env {
        name  = "MOTIONPRINT_CACHE_MAX"
        value = tostring(var.cache_max_bytes)
      }
      env {
        name  = "MOTIONPRINT_MAX_CONCURRENT"
        value = tostring(var.max_concurrent_renders)
      }
      env {
        name  = "RUST_LOG"
        value = "info"
      }

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle          = false
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        initial_delay_seconds = 2
        period_seconds        = 3
        failure_threshold     = 5
        timeout_seconds       = 2
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        period_seconds    = 15
        failure_threshold = 3
        timeout_seconds   = 5
      }
    }

    max_instance_request_concurrency = var.concurrency
    timeout                          = "${var.timeout_seconds}s"
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.main.name
  location = google_cloud_run_v2_service.main.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
