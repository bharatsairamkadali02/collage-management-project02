###############################################################################
# AWS RDS MySQL Database (Tier 2)
###############################################################################

resource "aws_db_subnet_group" "rds" {
  name        = "${var.project_name}-db-subnet-group"
  description = "Subnet group for RDS MySQL in private subnets"
  subnet_ids  = aws_subnet.rds_private[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

resource "aws_db_instance" "rds" {
  identifier        = "${var.project_name}-mysql"
  engine            = "mysql"
  engine_version    = "8.0"
  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 3306

  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = false
  skip_final_snapshot = true
  deletion_protection = false

  tags = {
    Name = "${var.project_name}-rds-mysql"
  }
}
