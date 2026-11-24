###############################################################################
# Infrastructure Outputs
###############################################################################

output "vpc_id" {
  description = "The ID of the unified VPC"
  value       = aws_vpc.main.id
}

output "eks_cluster_name" {
  description = "EKS Cluster Name"
  value       = aws_eks_cluster.main.name
}

output "eks_cluster_endpoint" {
  description = "EKS Control Plane Endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "rds_endpoint" {
  description = "RDS MySQL Host Endpoint (host:port)"
  value       = aws_db_instance.rds.endpoint
}

output "rds_address" {
  description = "RDS MySQL Hostname (without port)"
  value       = aws_db_instance.rds.address
}

output "rds_port" {
  description = "RDS MySQL Port"
  value       = aws_db_instance.rds.port
}

output "rds_db_name" {
  description = "RDS Database Name"
  value       = aws_db_instance.rds.db_name
}

output "rds_username" {
  description = "RDS Master Username"
  value       = aws_db_instance.rds.username
}

output "s3_bucket_name" {
  description = "S3 Bucket Name"
  value       = aws_s3_bucket.app_storage.bucket
}

output "aws_region" {
  description = "AWS Region"
  value       = var.aws_region
}
