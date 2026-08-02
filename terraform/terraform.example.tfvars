environment = "dev"
aws_region  = "eu-west-2"
key_name    = "your-key-pair-name"
# allowed_ssh_cidr = "YOUR_IP/32"

# RDS PostgreSQL — set a real password via TF_VAR_db_password or a secrets
# manager; never commit a real password to this file.
db_password = "changeme-use-a-real-secret"
