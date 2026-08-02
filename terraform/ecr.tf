resource "aws_ecr_repository" "northwind" {
  name                 = "northwind-delivery"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = true

  tags = {
    Name = "northwind-delivery"
  }
}

resource "aws_ecr_lifecycle_policy" "northwind" {
  repository = aws_ecr_repository.northwind.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 20 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 20
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
