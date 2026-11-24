###############################################################################
# Security Groups (EKS Nodes + RDS MySQL seamlessly connected)
###############################################################################

# -----------------------------------------------------------------------------
# EKS Cluster Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "eks_cluster" {
  name        = "${var.project_name}-eks-cluster-sg"
  description = "Security group for EKS control plane"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-eks-cluster-sg"
  }
}

# -----------------------------------------------------------------------------
# EKS Worker Nodes Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "eks_nodes" {
  name        = "${var.project_name}-eks-nodes-sg"
  description = "Security group for all nodes in the cluster"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name                                           = "${var.project_name}-eks-nodes-sg"
    "kubernetes.io/cluster/${var.eks_cluster_name}" = "owned"
  }
}

# Node-to-node internal communication
resource "aws_security_group_rule" "nodes_internal" {
  description              = "Allow nodes to communicate with each other"
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
  security_group_id        = aws_security_group.eks_nodes.id
  source_security_group_id = aws_security_group.eks_nodes.id
}

# Cluster-to-node communication
resource "aws_security_group_rule" "cluster_to_nodes" {
  description              = "Allow control plane to communicate with worker nodes"
  type                     = "ingress"
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  security_group_id        = aws_security_group.eks_nodes.id
  source_security_group_id = aws_security_group.eks_cluster.id
}

# Node-to-cluster communication
resource "aws_security_group_rule" "nodes_to_cluster" {
  description              = "Allow worker nodes to communicate with control plane"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.eks_cluster.id
  source_security_group_id = aws_security_group.eks_nodes.id
}

# -----------------------------------------------------------------------------
# RDS MySQL Security Group (ALLOWS 3306 DIRECTLY FROM EKS WORKER NODES)
# -----------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for RDS MySQL database"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow MySQL traffic directly from EKS worker nodes"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_group_id = aws_security_group.rds.id
    source_security_group_id = aws_security_group.eks_nodes.id
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}
