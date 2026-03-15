provider "aws" {
  region = "us-east-1"
  alias  = "us_east_1"
  default_tags {
    tags = {
      Project     = "motionprint"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
  default_tags {
    tags = {
      Project     = "motionprint"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = "us-central1"
}
