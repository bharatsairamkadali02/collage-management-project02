###############################################################################
# Input Variables for VPC, EC2, RDS MySQL, and S3 Infrastructure
###############################################################################

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name prefix for AWS resources"
  type        = string
  default     = "college-app"
}

# -----------------------------------------------------------------------------
# Networking (VPC, Subnets)
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the new VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Public subnet CIDR for the EC2 server (ap-south-1a)"
  type        = string
  default     = "10.10.1.0/24"
}

variable "private_subnet_az1_cidr" {
  description = "Private subnet CIDR 1 for RDS MySQL (ap-south-1a)"
  type        = string
  default     = "10.10.2.0/24"
}

variable "private_subnet_az2_cidr" {
  description = "Private subnet CIDR 2 for RDS MySQL (ap-south-1b)"
  type        = string
  default     = "10.10.3.0/24"
}

# -----------------------------------------------------------------------------
# EC2 Application Server
# -----------------------------------------------------------------------------

variable "ec2_instance_type" {
  description = "EC2 instance type for running Docker + Minikube Kubernetes"
  type        = string
  default     = "t3.medium"
}

variable "key_pair_name" {
  description = "Existing EC2 Key Pair name in AWS region for SSH access"
  type        = string
  default     = "laptopkeymumhp02"
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into EC2 (restrict to your IP/32 in production)"
  type        = string
  default     = "0.0.0.0/0"
}

# -----------------------------------------------------------------------------
# RDS MySQL Database
# -----------------------------------------------------------------------------

variable "db_name" {
  description = "Initial MySQL database name"
  type        = string
  default     = "college_management"
}

variable "db_username" {
  description = "Master username for RDS MySQL"
  type        = string
  default     = "admin"
}

variable "db_password" {
  description = "Master password for RDS MySQL (8-41 ASCII chars, excluding /, @, quotes, spaces)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8 && length(var.db_password) <= 41 && can(regex("^[!-~]+$", var.db_password)) && !can(regex("[/@\" ]", var.db_password))
    error_message = "db_password must be 8-41 printable ASCII characters and must not contain /, @, double quotes, or spaces."
  }
}

variable "db_instance_class" {
  description = "RDS DB instance class"
  type        = string
  default     = "db.t3.micro"
}

# -----------------------------------------------------------------------------
# S3 Storage
# -----------------------------------------------------------------------------

variable "s3_bucket_prefix" {
  description = "Prefix for globally unique S3 bucket name (random hex suffix is appended)"
  type        = string
  default     = "college-app-media"
}
