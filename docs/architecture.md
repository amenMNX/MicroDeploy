# Architecture

## Overview

MicroDeploy is a minimal multi-service backend application built to demonstrate
end-to-end DevOps practices: containerization, CI/CD, Kubernetes orchestration,
infrastructure as code, and observability.

## Components

| Component | Technology | Role |
|-----------|-----------|------|
| API Service | FastAPI (Python) | Serves HTTP requests, writes tasks to PostgreSQL |
| Worker Service | Python | Polls PostgreSQL, processes pending tasks |
| Database | PostgreSQL 15 | Persistent task storage |
| Container Runtime | Docker (multi-stage builds) | Packages each service into a portable image |
| CI/CD | GitHub Actions | Lint, test, build, scan, push on every commit |
| Image Registry | GitHub Container Registry (GHCR) | Stores versioned images |
| Orchestration | Kubernetes (Rancher Desktop) | Deploys, scales, and manages containers |
| IaC | Terraform + Helm | Provisions monitoring infrastructure declaratively |
| Metrics | Prometheus + Grafana | Collects and visualises service metrics |
| Logging | Loki + Promtail | Aggregates logs from all pods centrally |

## System Architecture Diagram

```
Developer
    |
    | git push
    v
GitHub Actions (CI/CD Pipeline)
    |-- ruff lint (api + worker)
    |-- pytest (api + worker)
    |-- docker build (api + worker)
    |-- trivy scan (api + worker)
    |-- docker push --> ghcr.io/amenmnx/microdeploy-api:latest
                        ghcr.io/amenmnx/microdeploy-worker:latest
                                        |
                                        | kubectl apply
                                        v
                          Kubernetes Cluster (Rancher Desktop)
                          |
                          |-- namespace: microdeploy
                          |       |-- Deployment: microdeploy-api (2 replicas)
                          |       |-- Deployment: microdeploy-worker (1 replica)
                          |       |-- Deployment: microdeploy-db (1 replica)
                          |       |-- Service: microdeploy-api
                          |       |-- Service: microdeploy-db
                          |       |-- ConfigMap: microdeploy-config
                          |       |-- Secret: microdeploy-secret
                          |       |-- ServiceMonitor: microdeploy-api
                          |
                          |-- namespace: monitoring
                                  |-- Prometheus (scrapes /metrics every 15s)
                                  |-- Grafana (dashboards on port 3000)
                                  |-- Alertmanager
                                  |-- Loki (log aggregation)
                                  |-- Promtail (log collector DaemonSet)
```

## Data Flow

### Request Flow
```
HTTP Client
    |
    v
microdeploy-api Service (ClusterIP :8080)
    |
    +--> Pod 1: microdeploy-api-xxxxx (FastAPI)
    |       |-- POST /tasks --> INSERT into PostgreSQL
    |       |-- GET  /tasks --> SELECT from PostgreSQL
    |       |-- GET  /health --> 200 OK
    |       |-- GET  /metrics --> Prometheus metrics
    |
    +--> Pod 2: microdeploy-api-yyyyy (FastAPI)
```

### Task Processing Flow
```
POST /tasks  -->  tasks table (status=pending)
                        |
                        | every 3 seconds
                        v
                  Worker Service
                        |
                        v
                  tasks table (status=done)
```

### Observability Flow
```
API Pods (/metrics)
    |
    | scrape every 15s
    v
Prometheus
    |
    | query (PromQL)
    v
Grafana Dashboards

All Pod Logs
    |
    | collect (Promtail DaemonSet)
    v
Loki
    |
    | query (LogQL)
    v
Grafana Explore
```

## Kubernetes Manifest Summary

| File | Kind | Purpose |
|------|------|---------|
| namespace.yaml | Namespace | Isolates all app resources |
| configmap.yaml | ConfigMap | Non-secret env vars (DB host, name, user) |
| secret.yaml | Secret | DB password (base64 encoded) |
| db-deployment.yaml | Deployment | PostgreSQL with readiness/liveness probes |
| db-service.yaml | Service | Internal DNS for DB (microdeploy-db:5432) |
| api-deployment.yaml | Deployment | FastAPI, 2 replicas, probes on /health |
| api-service.yaml | Service | Exposes API internally with app label for Prometheus |
| api-servicemonitor.yaml | ServiceMonitor | Tells Prometheus to scrape /metrics every 15s |
| worker-deployment.yaml | Deployment | Background task processor, 1 replica |
| init-sql-configmap.yaml | ConfigMap | Mounts init.sql into the Postgres container |

## CI/CD Pipeline Stages

```
push to main
    |
    v
[Job 1: test-and-lint]
    |-- pip install dependencies
    |-- ruff check api/   (linting)
    |-- pytest api/       (unit tests)
    |-- ruff check worker/
    |-- pytest worker/
    |
    v (on success)
[Job 2: build-scan-push]
    |-- docker build api  --> microdeploy-api:<sha>
    |-- docker build worker --> microdeploy-worker:<sha>
    |-- trivy scan api image (HIGH/CRITICAL CVEs)
    |-- trivy scan worker image
    |-- docker tag :latest
    |-- docker push to ghcr.io
```