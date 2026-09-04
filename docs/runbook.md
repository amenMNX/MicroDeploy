# Runbook: MicroDeploy Operations Guide

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Docker Desktop / Rancher Desktop | Container runtime | https://rancherdesktop.io |
| kubectl | Kubernetes CLI | bundled with Rancher Desktop |
| Terraform | Infrastructure provisioning | https://developer.hashicorp.com/terraform/install |
| Git | Source control | https://git-scm.com |
| PowerShell | Shell (Windows) | built-in |

---

## 1. Local Development (Docker Compose)

### Start the full stack locally
```bash
docker compose up --build
```

### Verify services are running
```bash
docker compose ps
```

### Test the API locally
```bash
# Health check
curl http://localhost:8081/health

# Create a task
curl -X POST http://localhost:8081/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "test task"}'

# List tasks
curl http://localhost:8081/tasks
```

### Stop the stack
```bash
docker compose down
```

### Stop and remove all data
```bash
docker compose down -v
```

---

## 2. Running Tests Locally

```bash
# API tests
cd api
pip install -r requirements.txt pytest httpx ruff
ruff check . --ignore E501
pytest -q

# Worker tests
cd ../worker
pip install -r requirements.txt pytest ruff
ruff check . --ignore E501
pytest -q
```

---

## 3. Kubernetes Deployment

### First-time setup — apply all manifests
```powershell
cd k8s
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f init-sql-configmap.yaml
kubectl apply -f db-deployment.yaml
kubectl apply -f db-service.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml
kubectl apply -f api-servicemonitor.yaml
kubectl apply -f worker-deployment.yaml
```

### Apply all at once (after first setup)
```powershell
kubectl apply -f k8s/
```

### Check all pods are running
```powershell
kubectl get pods -n microdeploy
```
Expected output:
```
NAME                                READY   STATUS    RESTARTS
microdeploy-api-xxxxxxxxx-xxxxx     1/1     Running   0
microdeploy-api-xxxxxxxxx-yyyyy     1/1     Running   0
microdeploy-db-xxxxxxxxx-xxxxx      1/1     Running   0
microdeploy-worker-xxxxxxxxx-xxxxx  1/1     Running   0
```

### Port-forward the API for local testing
```powershell
kubectl port-forward -n microdeploy svc/microdeploy-api 8081:8080
```

### Test the deployed API
```powershell
Invoke-RestMethod -Uri http://localhost:8081/health
Invoke-RestMethod -Uri http://localhost:8081/tasks
```

### Rolling restart (after new image push)
```powershell
kubectl rollout restart deployment/microdeploy-api -n microdeploy
kubectl rollout restart deployment/microdeploy-worker -n microdeploy
```

### Watch rollout status
```powershell
kubectl rollout status deployment/microdeploy-api -n microdeploy
```

---

## 4. Monitoring Stack (Terraform)

### First-time provisioning
```powershell
cd infra
terraform init
terraform apply
```

### Access Grafana
```powershell
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
```
Open: http://localhost:3000
Login: `admin` / `admin123`

### Access Prometheus
```powershell
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
```
Open: http://localhost:9090/targets

### Verify API is being scraped
Go to http://localhost:9090/targets and confirm:
`serviceMonitor/microdeploy/microdeploy-api/0` shows **2/2 up**

### Useful Grafana queries

| Query | Shows |
|-------|-------|
| `sum by (handler) (rate(http_requests_total{job="microdeploy-api"}[1m]))` | Requests/sec per endpoint |
| `sum(rate(http_requests_total{job="microdeploy-api"}[1m]))` | Total request rate |
| `sum by (pod) (rate(http_requests_total{job="microdeploy-api"}[1m]))` | Load per pod |

### View logs in Grafana (Loki)
1. Go to Explore → switch datasource to **Loki**
2. Query all app logs: `{namespace="microdeploy"}`
3. Query API logs only: `{namespace="microdeploy", container="api"}`
4. Query worker logs: `{namespace="microdeploy", container="worker"}`

---

## 5. Troubleshooting

### Pod won't start — CrashLoopBackOff
```powershell
# Check logs
kubectl logs -n microdeploy deployment/microdeploy-api

# Check events
kubectl describe pod -n microdeploy -l app=microdeploy-api
```

### API can't connect to database
```powershell
# Verify DB pod is ready
kubectl get pods -n microdeploy -l app=microdeploy-db

# Check DB logs
kubectl logs -n microdeploy deployment/microdeploy-db

# Verify configmap has correct DB_NAME
kubectl get configmap microdeploy-config -n microdeploy -o yaml
```

### Prometheus not scraping the API
```powershell
# Verify service has the correct label
kubectl get svc microdeploy-api -n microdeploy -o yaml | Select-String "labels" -Context 0,3

# Verify ServiceMonitor exists
kubectl get servicemonitor -n microdeploy

# Restart Prometheus operator
kubectl rollout restart deployment/monitoring-kube-prometheus-operator -n monitoring
```

### Grafana shows no data
1. Check Prometheus targets: http://localhost:9090/targets
2. If target is DOWN, check the service label (must have `app: microdeploy-api`)
3. If target is UP but Grafana is empty, check the time range (set to Last 15 minutes)
4. Generate traffic with the load loop and wait 1 minute for data to appear

### Terraform apply fails
```powershell
# Re-initialize providers
terraform init -upgrade

# Check cluster is reachable
kubectl get nodes

# Force refresh state
terraform refresh
```

### Image not pulling (ImagePullBackOff)
```powershell
# Check image name in deployment
kubectl describe pod -n microdeploy -l app=microdeploy-api | Select-String "Image"

# Verify image exists in registry
# Go to https://github.com/amenmnx?tab=packages
```

---

## 6. CI/CD Pipeline

The pipeline runs automatically on every push to `main`.

### Pipeline stages
1. **test-and-lint** — ruff lint + pytest for both services
2. **build-scan-push** — docker build → trivy scan → push to ghcr.io (on `main` only)

### Monitor pipeline
Go to your GitHub repository → **Actions** tab

### Manual trigger
```bash
git commit --allow-empty -m "trigger: force pipeline run"
git push
```

### After pipeline succeeds, redeploy
```powershell
kubectl rollout restart deployment/microdeploy-api -n microdeploy
kubectl rollout restart deployment/microdeploy-worker -n microdeploy
```