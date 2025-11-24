terraform {
  backend "s3" {
    bucket         = "fredgpt-backend-terraform-state"
    key            = "terraform/state.tfstate"
    region         = "us-east-1"
    dynamodb_table = "fredgpt-backend-terraform-locks"
    encrypt        = true
  }
}
