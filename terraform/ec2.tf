resource "aws_vpc" "northwind" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "northwind-vpc-${var.environment}"
  }
}

resource "aws_internet_gateway" "northwind" {
  vpc_id = aws_vpc.northwind.id

  tags = {
    Name = "northwind-igw-${var.environment}"
  }
}

resource "aws_subnet" "northwind" {
  vpc_id                  = aws_vpc.northwind.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "northwind-subnet-${var.environment}"
  }
}

resource "aws_route_table" "northwind" {
  vpc_id = aws_vpc.northwind.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.northwind.id
  }

  tags = {
    Name = "northwind-rt-${var.environment}"
  }
}

resource "aws_route_table_association" "northwind" {
  subnet_id      = aws_subnet.northwind.id
  route_table_id = aws_route_table.northwind.id
}

resource "aws_security_group" "northwind" {
  name        = "northwind-sg-${var.environment}"
  description = "Security group for Northwind delivery EC2 host"
  vpc_id      = aws_vpc.northwind.id

  ingress {
    description = "HTTP delivery service"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "northwind-sg-${var.environment}"
  }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_iam_role" "ec2_role" {
  name = "northwind-ec2-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "northwind-ec2-profile-${var.environment}"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "northwind" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  subnet_id              = aws_subnet.northwind.id
  vpc_security_group_ids = [aws_security_group.northwind.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    app_port     = var.app_port
    database_url = "postgresql+psycopg2://${var.db_username}:${var.db_password}@${aws_db_instance.northwind.address}:5432/${var.db_name}"
  }))

  tags = {
    Name = "northwind-delivery-${var.environment}"
  }
}
