###############################################################################
# Outputs for VPC, EC2, RDS MySQL, and S3
###############################################################################

output "vpc_id" {
  description = "New VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Public subnet ID (EC2)"
  value       = aws_subnet.public.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (RDS)"
  value       = [aws_subnet.private_az1.id, aws_subnet.private_az2.id]
}

output "ec2_instance_id" {
  description = "New EC2 instance ID"
  value       = aws_instance.app_server.id
}

output "ec2_public_ip" {
  description = "Elastic Public IP of the EC2 server"
  value       = aws_eip.app_eip.public_ip
}

output "ssh_command" {
  description = "Command to SSH into the EC2 server"
  value       = "ssh -i ${var.key_pair_name}.pem ubuntu@${aws_eip.app_eip.public_ip}"
}

output "rds_endpoint" {
  description = "New RDS MySQL endpoint (host:port)"
  value       = aws_db_instance.rds.endpoint
}

output "rds_address" {
  description = "New RDS MySQL hostname (use as DB_HOST / DATABASE_HOST)"
  value       = aws_db_instance.rds.address
}

output "rds_port" {
  description = "RDS MySQL port"
  value       = aws_db_instance.rds.port
}

output "rds_db_name" {
  description = "RDS database name"
  value       = aws_db_instance.rds.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.rds.username
}

output "s3_bucket_name" {
  description = "New S3 bucket name (use as S3_BUCKET_NAME)"
  value       = aws_s3_bucket.app_storage.bucket
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "app_url" {
  description = "Application URL once container runs on port 8080"
  value       = "http://${aws_eip.app_eip.public_ip}:8080"
}
