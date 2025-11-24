terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ------------------------------
# ECR Repository
# ------------------------------
resource "aws_ecr_repository" "backend" {
  name = "fredgpt-backend"
}

# ------------------------------
# Secrets (SSM Parameter Store)
# Replace the placeholder values or import existing parameters.
# ------------------------------
resource "aws_ssm_parameter" "fred_api_key" {
  name  = "/fredgpt/FRED_API_KEY"
  type  = "SecureString"
  value = var.fred_api_key
}

resource "aws_ssm_parameter" "pg_host" {
  name  = "/fredgpt/PG_HOST"
  type  = "SecureString"
  value = var.pg_host
}

resource "aws_ssm_parameter" "pg_name" {
  name  = "/fredgpt/PG_NAME"
  type  = "SecureString"
  value = var.pg_name
}

resource "aws_ssm_parameter" "pg_user" {
  name  = "/fredgpt/PG_USER"
  type  = "SecureString"
  value = var.pg_user
}

resource "aws_ssm_parameter" "pg_pass" {
  name  = "/fredgpt/PG_PASS"
  type  = "SecureString"
  value = var.pg_pass
}

# ------------------------------
# IAM Roles for App Runner
# ------------------------------

# Allows App Runner to pull from ECR
resource "aws_iam_role" "apprunner_ecr" {
  name = "AppRunnerECRAccessRole"
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "build.apprunner.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# Instance role used inside your container (Bedrock, Logs, SSM)
resource "aws_iam_role" "apprunner_instance" {
  name = "AppRunner-FredGPT-InstanceRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "tasks.apprunner.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_access" {
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

resource "aws_iam_role_policy_attachment" "logs_access" {
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_role_policy_attachment" "ssm_read" {
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
}

# ------------------------------
# App Runner Service
# ------------------------------
resource "aws_apprunner_service" "backend" {
  service_name = "fredgpt-backend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr.arn
    }

    image_repository {
      image_configuration {
        port = "8000"

        # Non-secret env vars
        runtime_environment_variables = {
          AWS_REGION = "us-east-1"
        }

        # Secrets pulled from SSM
        runtime_environment_secrets = {
          FRED_API_KEY = aws_ssm_parameter.fred_api_key.arn
          PG_HOST      = aws_ssm_parameter.pg_host.arn
          PG_NAME      = aws_ssm_parameter.pg_name.arn
          PG_USER      = aws_ssm_parameter.pg_user.arn
          PG_PASS      = aws_ssm_parameter.pg_pass.arn
        }
      }

      image_identifier      = "${aws_ecr_repository.backend.repository_url}:latest"
      image_repository_type = "ECR"
    }
  }

  instance_configuration {
    cpu               = "1024"
    memory            = "2048"
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/"
    interval            = 20
    timeout             = 10
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = "arn:aws:apprunner:us-east-1:112393354239:autoscalingconfiguration/DefaultConfiguration/1/00000000000000000000000000000001"

  observability_configuration {
    observability_enabled = false
  }
}

# ------------------------------
# Variables
# Provide these at apply time (e.g., TF_VAR_fred_api_key=...)
# ------------------------------
variable "fred_api_key" {
  type      = string
  sensitive = true
}

variable "pg_host" {
  type      = string
  sensitive = true
}

variable "pg_name" {
  type    = string
  default = "fomc"
}

variable "pg_user" {
  type    = string
  default = "postgres"
}

variable "pg_pass" {
  type      = string
  sensitive = true
}
