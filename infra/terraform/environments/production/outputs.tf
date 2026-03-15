output "aws_endpoints" {
  value = {
    us_east_1 = module.aws_us_east_1.alb_dns_name
    us_west_2 = module.aws_us_west_2.alb_dns_name
  }
}

output "gcp_endpoints" {
  value = {
    us_central1  = module.gcp_us_central1.cloud_run_uri
    europe_west1 = module.gcp_europe_west1.cloud_run_uri
  }
}

output "gcp_global_lb_ip" {
  value = google_compute_global_forwarding_rule.main.ip_address
}

output "aws_route53_nameservers" {
  value = aws_route53_zone.main.name_servers
}
