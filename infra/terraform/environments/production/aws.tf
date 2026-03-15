module "aws_us_east_1" {
  source = "../../modules/aws-region"
  providers = {
    aws = aws.us_east_1
  }

  aws_region      = "us-east-1"
  container_image = "${module.aws_us_east_1.ecr_repository_url}:${var.image_tag}"
  certificate_arn = var.aws_certificate_arn_us_east_1
  vpc_cidr        = "10.0.0.0/16"

  task_cpu               = 4096
  task_memory            = 8192
  max_concurrent_renders = 4
  desired_count          = 2
  min_capacity           = 2
  max_capacity           = 20
}

module "aws_us_west_2" {
  source = "../../modules/aws-region"
  providers = {
    aws = aws.us_west_2
  }

  aws_region      = "us-west-2"
  container_image = "${module.aws_us_west_2.ecr_repository_url}:${var.image_tag}"
  certificate_arn = var.aws_certificate_arn_us_west_2
  vpc_cidr        = "10.1.0.0/16"

  task_cpu               = 4096
  task_memory            = 8192
  max_concurrent_renders = 4
  desired_count          = 2
  min_capacity           = 2
  max_capacity           = 20
}
