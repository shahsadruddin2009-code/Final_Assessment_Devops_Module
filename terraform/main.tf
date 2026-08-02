terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "northwind-terraform-state-2513806"
    key            = "northwind-delivery/terraform.tfstate"
    region         = "us-east-2"
    encrypt        = true
    dynamodb_table = "northwind-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "NorthwindDelivery"
      Environment = var.environment
      Owner       = "Shahzad Sadruddin"
      StudentID   = "2513806"
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {}
