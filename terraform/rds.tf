resource "aws_db_subnet_group" "northwind" {
  name       = "northwind-db-subnet-${var.environment}"
  subnet_ids = [aws_subnet.northwind.id, aws_subnet.northwind_secondary.id]

  tags = {
    Name = "northwind-db-subnet-${var.environment}"
  }
}

# RDS requires at least two subnets in different AZs for its subnet group,
# even for a single-AZ instance, so a second subnet is provisioned alongside
# the one the EC2 host uses.
resource "aws_subnet" "northwind_secondary" {
  vpc_id                  = aws_vpc.northwind.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = false

  tags = {
    Name = "northwind-subnet-secondary-${var.environment}"
  }
}

resource "aws_security_group" "northwind_db" {
  name        = "northwind-db-sg-${var.environment}"
  description = "Allow PostgreSQL access from the Northwind EC2 host only"
  vpc_id      = aws_vpc.northwind.id

  ingress {
    description     = "PostgreSQL from the app EC2 instance"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.northwind.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "northwind-db-sg-${var.environment}"
  }
}

resource "aws_db_instance" "northwind" {
  identifier             = "northwind-delivery-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.northwind.name
  vpc_security_group_ids = [aws_security_group.northwind_db.id]

  publicly_accessible = false
  skip_final_snapshot = true
  storage_encrypted   = true
  multi_az            = false

  tags = {
    Name = "northwind-delivery-db-${var.environment}"
  }
}
