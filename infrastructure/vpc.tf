###############################################################################
# VPC & Networking for Unified EKS + RDS Architecture
###############################################################################

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name                                           = "${var.project_name}-vpc"
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "shared"
  }
}

# -----------------------------------------------------------------------------
# Internet Gateway (for Public Subnets)
# -----------------------------------------------------------------------------
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# -----------------------------------------------------------------------------
# Public Subnets (For AWS Load Balancers / Ingress)
# -----------------------------------------------------------------------------
resource "aws_subnet" "public" {
  count                   = length(var.public_subnets)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnets[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                                           = "${var.project_name}-public-subnet-${count.index + 1}"
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "shared"
    "kubernetes.io/role/elb"                       = "1"
  }
}

# -----------------------------------------------------------------------------
# Private Subnets (For EKS Worker Nodes)
# -----------------------------------------------------------------------------
resource "aws_subnet" "eks_private" {
  count             = length(var.eks_private_subnets)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.eks_private_subnets[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name                                           = "${var.project_name}-eks-private-subnet-${count.index + 1}"
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"              = "1"
  }
}

# -----------------------------------------------------------------------------
# Private Subnets (For RDS MySQL Multi-AZ)
# -----------------------------------------------------------------------------
resource "aws_subnet" "rds_private" {
  count             = length(var.rds_private_subnets)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.rds_private_subnets[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-rds-private-subnet-${count.index + 1}"
  }
}

# -----------------------------------------------------------------------------
# NAT Gateway & Elastic IP (Allows EKS Nodes to pull images from Docker Hub)
# -----------------------------------------------------------------------------
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "${var.project_name}-nat-gw"
  }

  depends_on = [aws_internet_gateway.igw]
}

# -----------------------------------------------------------------------------
# Route Tables & Associations
# -----------------------------------------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

resource "aws_route_table_association" "eks_private" {
  count          = length(aws_subnet.eks_private)
  subnet_id      = aws_subnet.eks_private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table" "rds" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-rds-rt"
  }
}

resource "aws_route_table_association" "rds_private" {
  count          = length(aws_subnet.rds_private)
  subnet_id      = aws_subnet.rds_private[count.index].id
  route_table_id = aws_route_table.rds.id
}
