output "ec2_public_ip" {
  description = "Public IP of the Northwind delivery EC2 instance"
  value       = aws_instance.northwind.public_ip
}

output "ec2_instance_id" {
  description = "Instance ID of the provisioned EC2 host"
  value       = aws_instance.northwind.id
}

output "service_url" {
  description = "URL to reach the running delivery service"
  value       = "http://${aws_instance.northwind.public_ip}:${var.app_port}"
}

output "db_endpoint" {
  description = "RDS PostgreSQL connection endpoint (host:port)"
  value       = aws_db_instance.northwind.endpoint
}

output "db_address" {
  description = "RDS PostgreSQL host address"
  value       = aws_db_instance.northwind.address
}
