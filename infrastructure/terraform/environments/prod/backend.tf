terraform {
  backend "s3" {
    bucket         = "alx-monitoring-terraform-state-411683670812"
    key            = "ltt/prod/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}
