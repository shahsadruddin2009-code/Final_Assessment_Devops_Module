#!/bin/bash
set -euo pipefail

# Update and install Docker on Amazon Linux 2023
dnf update -y
dnf install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Pull and run the latest Northwind delivery image.
# In production this tag is supplied by the CI/CD pipeline.
docker pull "ghcr.io/shahzad-sadruddin/northwind-delivery:latest"

docker run -d \
  --name northwind-delivery \
  --restart unless-stopped \
  -p ${app_port}:${app_port} \
  -e PORT=${app_port} \
  -e DATABASE_URL="${database_url}" \
  ghcr.io/shahzad-sadruddin/northwind-delivery:latest
