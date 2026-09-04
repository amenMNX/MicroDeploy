# MicroDeploy — End-to-End DevOps Pipeline

A one-month internship-style DevOps project demonstrating containerization, CI/CD, Kubernetes orchestration, infrastructure as code, and observability on a minimal multi-service application.

## Stack

| Layer | Technology |
|-------|-----------|
| Application | FastAPI (API) + Python (Worker) + PostgreSQL |
| Containers | Docker with multi-stage builds |
| CI/CD | GitHub Actions (lint → test → build → scan → push) |
| Orchestration | Kubernetes (Rancher Desktop) |
| IaC | Terraform + Helm |
| Metrics | Prometheus + Grafana |
| Logging | Loki + Promtail |
| Registry | GitHub Container Registry (GHCR) |
| Security | Trivy image scanning |

## Project Structure

```
.
├── api/                    # FastAPI service (tasks CRUD + /metrics)
│   ├── main.py
│   ├── test_main.py
│   ├── requirements.txt
│   └── Dockerfile
├── worker/                 # Background task processor
│   ├── main.py
│   ├── test_main.py
│   ├── requirements.txt
│   └── Dockerfile
├── db/
│   └── init.sql            # PostgreSQL schema
├── k8s/                    # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── api-deployment.yaml
│   ├── api-service.yaml
│   ├── api-servicemonitor.yaml
│   ├── db-deployment.yaml
│   ├── db-service.yaml
│   ├── worker-deployment.yaml
│   └── init-sql-configmap.yaml
├── infra/                  # Terraform (Prometheus + Grafana + Loki)
│   ├── main.tf
│   └── providers.tf
├── docs/
│   ├── architecture.md
│   ├── runbook.md
│   └── load-test-results.md
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Quick Start (Local)

```bash
docker compose up --build
```

API available at http://localhost:8080

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Service info |
| GET | /health | Health check |
| POST | /tasks | Create a task |
| GET | /tasks | List all tasks |
| GET | /metrics | Prometheus metrics |

## Kubernetes Deployment

```powershell
kubectl apply -f k8s/
```

## Monitoring

```powershell
# Provision Prometheus + Grafana + Loki
cd infra && terraform apply

# Access Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# Open http://localhost:3000  (admin / admin123)

# Access Prometheus
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

## Documentation

- [Architecture](docs/architecture.md) — system components and data flow
- [Runbook](docs/runbook.md) — how to build, deploy, and troubleshoot
- [Load Test Results](docs/load-test-results.md) — observed performance under load