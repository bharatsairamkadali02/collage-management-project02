###############################################################################
# 5. EC2 Docker Host + IAM Role for S3 + Elastic IP
###############################################################################

# Latest Ubuntu 22.04 LTS AMI in the configured region
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_key_pair" "ec2" {
  key_name = var.key_pair_name
}

# -----------------------------------------------------------------------------
# IAM Role & Instance Profile (Grants EC2 & Docker Containers S3 Access)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_role" {
  name_prefix        = "${var.project_name}-ec2-role-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

data "aws_iam_policy_document" "s3_access" {
  statement {
    sid    = "S3ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.app_storage.arn}/*"]
  }

  statement {
    sid    = "S3BucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.app_storage.arn]
  }
}

resource "aws_iam_policy" "s3_access" {
  name_prefix = "${var.project_name}-s3-policy-"
  description = "Allow EC2 Docker containers to read/write the S3 bucket"
  policy      = data.aws_iam_policy_document.s3_access.json
}

resource "aws_iam_role_policy_attachment" "ec2_s3" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name_prefix = "${var.project_name}-ec2-profile-"
  role        = aws_iam_role.ec2_role.name
}

# -----------------------------------------------------------------------------
# EC2 Instance
# -----------------------------------------------------------------------------

resource "aws_instance" "app_server" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.ec2_instance_type

  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.ec2_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  key_name                    = data.aws_key_pair.ec2.key_name
  associate_public_ip_address = true

  user_data = file("${path.module}/user_data.sh")

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 25
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "${var.project_name}-root-volume"
    }
  }

  # hop_limit = 4 allows Pods inside Minikube (Docker driver) on EC2 to fetch IAM role credentials for S3 via IMDSv2
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 4
  }

  tags = {
    Name = "${var.project_name}-ec2-server"
  }

  lifecycle {
    ignore_changes = [user_data]
  }
}

# -----------------------------------------------------------------------------
# Elastic IP
# -----------------------------------------------------------------------------

resource "aws_eip" "app_eip" {
  instance = aws_instance.app_server.id
  domain   = "vpc"

  depends_on = [aws_internet_gateway.igw]

  tags = {
    Name = "${var.project_name}-eip"
  }
}
