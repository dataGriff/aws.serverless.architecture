terraform {
  required_version = ">= 1.6"
  required_providers {
    aws   = { source = "hashicorp/aws", version = ">= 5.0" }
    awscc = { source = "hashicorp/awscc", version = ">= 1.104.0" }
  }
}

# Spike D runs in eu-west-1: the Custom Event Bus has no endpoint in eu-west-2 (checked 2026-10-04).
variable "region" {
  type    = string
  default = "eu-west-1"
}

provider "aws" {
  region = var.region
}

provider "awscc" {
  region = var.region
}
