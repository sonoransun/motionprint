resource "aws_route53_zone" "main" {
  name = var.domain_name
}

resource "aws_route53_record" "aws_us_east_1" {
  zone_id        = aws_route53_zone.main.zone_id
  name           = "api.${var.domain_name}"
  type           = "A"
  set_identifier = "aws-us-east-1"

  alias {
    name                   = module.aws_us_east_1.alb_dns_name
    zone_id                = module.aws_us_east_1.alb_zone_id
    evaluate_target_health = true
  }

  latency_routing_policy {
    region = "us-east-1"
  }
}

resource "aws_route53_record" "aws_us_west_2" {
  zone_id        = aws_route53_zone.main.zone_id
  name           = "api.${var.domain_name}"
  type           = "A"
  set_identifier = "aws-us-west-2"

  alias {
    name                   = module.aws_us_west_2.alb_dns_name
    zone_id                = module.aws_us_west_2.alb_zone_id
    evaluate_target_health = true
  }

  latency_routing_policy {
    region = "us-west-2"
  }
}
