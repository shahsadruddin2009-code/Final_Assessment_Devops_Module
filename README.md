# Northwind Logistics — DevOps Delivery Tracking Solution

This repository contains the complete DevOps artefact for the CSO7024 final
project. It packages the original Python delivery-tracking service with an
automated test suite, CI/CD pipeline, Terraform infrastructure, Ansible
configuration management, container images, and Kubernetes orchestration. A Go
comparison service is also included.

## Scenario

Northwind Logistics is the mid-sized European logistics provider from the module's
case studies. Among its systems is the delivery-tracking service in this
repository, which lets operators and customers check the status of a parcel in
transit. Acting as the DevOps engineer for this service, this repository builds
a complete toolchain around the application: version control, automated testing,
a CI/CD pipeline, configuration management/IaC, and containerised, orchestrated
deployment.

## What the service does

Both the Python and Go implementations expose the same small HTTP API:

| Method | Path                    | Description                                   |
| ------ | ----------------------- | ---------------------------------------------- |
| GET    | `/`                     | Service information and the list of endpoints |
| GET    | `/health`               | Health check, always returns HTTP 200         |
| GET    | `/metrics`              | Request counters and delivery statistics      |
| GET    | `/deliveries`           | All deliveries, as JSON                       |
| GET    | `/deliveries?status=X`  | Deliveries filtered by status                 |
| GET    | `/deliveries/{id}`      | One delivery as JSON, or HTTP 404 if unknown  |

## Data persistence — PostgreSQL

Delivery records are stored in a real database, not in process memory, so the
service does not accumulate an unbounded, ever-growing dataset in RAM and every
replica reads from a single source of truth:

* **Python** ([app/db.py](app/db.py), [app/data.py](app/data.py)) uses
  SQLAlchemy Core. Every function (`all_deliveries`, `find_delivery`,
  `filter_by_status`, `count_by_status`) pulls exactly the rows it needs from
  the database on demand — nothing is cached in memory beyond a single
  request. The backend is selected by the `DATABASE_URL` environment
  variable:
  * unset → SQLite (zero-setup default for local development and the
    automated test suite; in-memory for tests, a local file otherwise).
  * `postgresql+psycopg2://user:pass@host:5432/db` → PostgreSQL, used in
    Docker Compose, Kubernetes, and the AWS/Terraform deployment.
* **Go** ([go/pkg/store](go/pkg/store)) mirrors the same idea behind a small
  `Store` interface: `NewMemoryStore()` (default, used by `go test`) or
  `NewPostgresStore(dsn)` (used automatically by `cmd/server` when
  `DATABASE_URL` is set), both implementing identical `All`/`Find`/
  `FilterByStatus`/`CountByStatus` methods.

Both the [Docker Compose file](docker-compose.yml) and the
[Kubernetes manifests](k8s/postgres.yaml) run a PostgreSQL container alongside
the app so this works out of the box. On AWS, [Terraform](terraform/rds.tf)
provisions a managed RDS PostgreSQL instance instead, reachable only from the
EC2 host's security group.

One consequence worth noting for the technical report: the Kubernetes
[deployment](k8s/deployment.yaml) runs **2 replicas**, but because both now
read from the same PostgreSQL instance rather than independent in-memory
stores, they see a consistent view of the data — including for any future
write endpoints (e.g. the Go store's design extends naturally to
`Create`/`UpdateStatus` against the shared database).

## Repository layout

```
app/                       Original Python service (data + HTTP handler + db.py)
tests/                     pytest unit, integration and performance tests
.github/workflows/         GitHub Actions CI/CD pipeline
terraform/                 AWS EC2 + RDS PostgreSQL infrastructure as code
ansible/                   Ansible playbook + vault-encrypted AWS/DB credentials
scripts/                   Python helpers (vault encryption, dashboard generator)
k8s/                       Kubernetes manifests (app + Postgres) + smoke-test Job
go/                        Go comparison service with equivalent endpoints + pkg/store
report/                    Generated technical report (PDF) + architecture diagram
Dockerfile                 Python container image
go.Dockerfile              Go container image (distroless)
docker-compose.yml         Local dev: app + PostgreSQL
run.py / __main__.py       Local Python entry points
requirements.txt           Python dependencies
```

## Quick start — run locally

Without a database configured, both services fall back to a zero-setup
backend (SQLite for Python, in-memory for Go):

```bash
python -m app            # Python service on port 8000 (SQLite file db)
# or
cd go && go run ./cmd/server   # Go service on port 8000 (in-memory store)
```

To run against PostgreSQL locally instead:

```bash
docker compose up --build
```

Then, in another terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/deliveries
curl http://localhost:8000/deliveries?status=delivered
curl http://localhost:8000/deliveries/NL-1002
curl http://localhost:8000/metrics
```

The port can be changed with the `PORT` environment variable, for example
`PORT=9000 python -m app`.

## Run tests

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q

cd go
go test ./...
```

Tests run against in-memory SQLite/an in-memory store by default (no external
dependency required). Set `TEST_POSTGRES_URL` (Python) or `TEST_POSTGRES_URL`
(Go, as a `postgres://` DSN) to additionally run the Postgres integration
tests against a real instance — the CI pipeline does this automatically using
a Postgres service container.

## Build and run containers

```bash
docker build -t northwind-delivery:py .
docker run -p 8000:8000 northwind-delivery:py

docker build -f go.Dockerfile -t northwind-delivery:go .
docker run -p 8000:8000 northwind-delivery:go
```

## Provision AWS infrastructure with Terraform

```bash
cd terraform
cp terraform.example.tfvars terraform.tfvars
# edit terraform.tfvars with your AWS key pair name, IP range, and db_password
terraform init
terraform plan
terraform apply
```

This provisions the EC2 host and an RDS PostgreSQL instance (`terraform/rds.tf`),
reachable only from that EC2 host's security group. `terraform output db_address`
gives the RDS endpoint needed by Ansible.

## Configure the host with Ansible

```bash
# Create the encrypted AWS credentials file first
python scripts/encrypt_aws_credentials.py

# Edit ansible/group_vars/database.yml with the RDS endpoint from Terraform,
# and encrypt the real db_password with:
#   ansible-vault encrypt_string --name 'db_password' <password>

# Edit ansible/inventory.ini with the EC2 public IP from Terraform
cd ansible
ansible-playbook -i inventory.ini playbook.yml --ask-vault-pass
```

The playbook deploys the container with `DATABASE_URL` pointing at the RDS
instance, so the EC2-hosted service reads and writes through PostgreSQL.

## Deploy to Kubernetes

```bash
./k8s/deploy.sh
```

This applies the ConfigMap, a PostgreSQL Deployment/PVC/Service/Secret
([k8s/postgres.yaml](k8s/postgres.yaml)), the app Deployment/Service, and a
smoke-test Job — waiting for Postgres to be ready before rolling out the app,
then for the whole rollout to complete. See
[Data persistence](#data-persistence--postgresql) above for how the app finds
the database via `DATABASE_URL`.

## Technical report

The CSO7024 written report (architecture, evidence, evaluation, and
professional-practice reflection) is generated as a PDF with an embedded
pipeline diagram:

```bash
python -m pip install reportlab matplotlib
python scripts/generate_report.py
```

This writes `report/Technical_Report_Shahzad_Sadruddin_2513806.pdf` and
`report/architecture-diagram.png`.

## Deploying this service locally: two things to plan for

**A cloud-hosted CI runner cannot reach your local cluster.** GitHub Actions'
hosted runners have no network route to a minikube or k3s cluster on your own
machine. The pipeline builds the image, runs the tests and pushes the image to
GHCR; the `deploy` job then uses a **self-hosted runner** on this machine so
`kubectl apply` can reach the local cluster.

**"Automating the environment" with no cloud account.** Terraform provisions a
real AWS EC2 host (see `terraform/`) as the IaC path for this project. Ansible
then configures that host — installing Docker and deploying the container —
using vault-encrypted AWS credentials, keeping the IaC and configuration
management steps clearly separated from the local Kubernetes deployment.

## CI/CD pipeline

[.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml) runs on every push and
PR:

1. Lints the Python code with `ruff`.
2. Runs the pytest suite (with a Postgres service container) and the Go test
   suite (`go vet` + `go test -race -cover`, also against a Postgres service
   container).
3. Builds and pushes Python and Go container images to GHCR.
4. Smoke-tests the Python container.
5. Uses a self-hosted runner on `main` to deploy to the local Kubernetes cluster.
6. Generates an HTML dashboard with run metadata, timestamps, and test results.

## Security notes

* `ansible/group_vars/aws_credentials.yml` and the `db_password` entry in
  `ansible/group_vars/database.yml` are Ansible-Vault-encrypted — never commit
  plaintext secrets.
* `vault_pass.txt` is ignored by Git and must be created locally if you run
  `ansible-vault` with `--vault-password-file`.
* Terraform remote state is stored in S3 with DynamoDB locking; configure the
  backend bucket/table before first use.
* The RDS instance (`terraform/rds.tf`) is not publicly accessible; its
  security group only permits inbound PostgreSQL traffic from the app EC2
  host's security group.
* The Kubernetes Postgres credentials in `k8s/postgres.yaml` are placeholders —
  replace them (and the matching `DATABASE_URL`) before deploying to a shared
  cluster.

## Evaluation notes for the report

The toolchain connects as follows:

* **LO3 (version control):** Feature branches, PR checks, and commit SHA-tagged
  container images support collaborative development.
* **LO4 (CI/CD):** GitHub Actions builds, tests, pushes, smoke-tests, and
  deploys the application end-to-end.
* **LO5 (configuration management):** Ansible installs Docker and deploys the
  container using vault-encrypted AWS credentials.
* **LO6 (containerisation/orchestration):** Docker images include health checks;
  Kubernetes manifests provide replicated deployment, service exposure, probes,
  and smoke tests.
* **LO7 (current practice):** GitHub Actions, GHCR, Terraform, Ansible Vault,
  Kubernetes probes, and the Go comparison service reflect current DevOps
  tooling.

## Author

**Shahzad Sadruddin**  
Student ID: 2513806

## License

This project is provided for educational purposes only as part of the CSO7024 Final Assessment. Unauthorized distribution, reproduction, or use of this material outside of the educational context is prohibited.

**Educational Purpose Only** — All code, documentation, and artefacts in this repository are the intellectual property of the educational institution and may only be used by authorized students and faculty for coursework and assessment purposes.
