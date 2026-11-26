###############################################################################
# 4. RDS MySQL Database (Private Subnets, Accessible Only From EC2)
###############################################################################

resource "aws_db_subnet_group" "rds" {
  name        = "${var.project_name}-db-subnet-group-${random_id.suffix.hex}"
  description = "Private subnet group for RDS MySQL"
  subnet_ids = [
    aws_subnet.private_az1.id,
    aws_subnet.private_az2.id,
  ]

  tags = {
    Name = "${var.project_name}-db-subnet-group-${random_id.suffix.hex}"
  }
}

resource "aws_db_instance" "rds" {
  identifier = "${var.project_name}-rds-${random_id.suffix.hex}"

  engine         = "mysql"
  engine_version = "8.0"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 3306

  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  publicly_accessible        = false
  multi_az                   = false
  deletion_protection        = false
  backup_retention_period    = 1
  auto_minor_version_upgrade = true
  skip_final_snapshot        = true
  performance_insights_enabled = false

  tags = {
    Name = "${var.project_name}-rds-${random_id.suffix.hex}"
  }
}
