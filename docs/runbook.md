# Runbook: MicroDeploy Operations Guide

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Rancher Desktop | Container runtime + local Kubernetes | https://rancherdesktop.io |
| kubectl | Kubernetes CLI | bundled with Rancher Desktop |
| kubeseal | Encrypts secrets for Sealed Secrets | https://github.com/bitnami-labs/sealed-secrets/releases |
| Terraform | Infrastructure provisioning (monitoring stack) | https://developer.hashicorp.com/terraform/install |
| Git | Source control | https://git-scm.com |
| PowerShell | Shell (Windows) | built-in |

**Important:** day-to-day deployment is GitOps-driven. You do not run
`kubectl apply` against `gitops/manifests/` directly — ArgoCD does that.
`kubectl` is still used constantly for *reading* cluster state and for
one-time setup (installing ArgoCD itself, generating Sealed Secrets).

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
curl http://localhost:8081/health
curl -X POST http://localhost:8081/tasks -H "Content-Type: application/json" -d '{"title": "test task"}'
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
cd api
pip install -r requirements.txt pytest httpx ruff
ruff check . --ignore E501
pytest -q

cd ../worker
pip install -r requirements.txt pytest ruff
ruff check . --ignore E501
pytest -q
```

---

## 3. GitOps Deployment (ArgoCD)

### One-time: install ArgoCD
```powershell
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s
```

### One-time: apply the ApplicationSet
```powershell
kubectl apply -f gitops\apps\api-appset.yaml
```
This generates two Applications, `api-dev` and `api-prod`, from one template.
You do not create or edit per-environment Application files by hand.

### Everyday dev deploy
Just push to `main`. CI builds, scans, pushes the image, and auto-commits the
new tag to `gitops/manifests/dev/kustomization.yaml`. ArgoCD's `api-dev`
Application notices the new commit and syncs automatically — nothing to run
by hand.

### Promoting to prod
Prod tracks the git tag `v1.0.0`, not `main`. Nothing reaches prod until you
deliberately move that tag:
```powershell
git log --oneline -5            # pick the commit you want in prod
git tag -f v1.0.0 <commit-sha>
git push origin v1.0.0 --force
```
ArgoCD's `api-prod` Application notices the tag moved and syncs automatically.

### Generating a prod Sealed Secret (first time, or if the DB password changes)
Sealed Secrets are encrypted per-namespace — a dev-sealed secret cannot be
copied to prod, it must be re-sealed:
```powershell
kubectl create secret generic microdeploy-secret `
  --namespace microdeploy-prod `
  --from-literal=DB_PASSWORD='<real password>' `
  --dry-run=client -o yaml | kubeseal --format yaml > gitops\manifests\prod\sealed-secret.yaml
```
Commit and push the resulting file like any other change.

### Check application status
```powershell
kubectl get application -n argocd
```
Expect `api-dev` and `api-prod` both `Synced` / `Healthy`. `OutOfSync` or
`Degraded` for more than a minute or two is worth investigating — see
Troubleshooting below.

### Force a refresh if an Application seems stuck
```powershell
kubectl annotate application api-prod -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

### Open the ArgoCD UI
```powershell
kubectl port-forward svc/argocd-server -n argocd 8080:443
```
Open `https://localhost:8080` (accept the self-signed cert warning).
Username: `admin`. Password:
```powershell
$encoded = kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encoded))
```
(This initial-admin secret only exists until the admin password is changed
for the first time; if it 404s, you've already rotated it.)

### Check pods directly (either environment)
```powershell
kubectl get pods -n microdeploy        # dev
kubectl get pods -n microdeploy-prod   # prod
```

### Port-forward the API for local testing
```powershell
kubectl port-forward -n microdeploy svc/microdeploy-api 8081:8080        # dev
kubectl port-forward -n microdeploy-prod svc/microdeploy-api 8082:8080   # prod
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
Username: `admin`
Password:
```powershell
$encoded = kubectl get secret monitoring-grafana -n monitoring -o jsonpath="{.data.admin-password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encoded))
```

### Access Prometheus
```powershell
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
```
Open: http://localhost:9090/targets

### Verify both environments' APIs are being scraped
At http://localhost:9090/targets, confirm:
- `serviceMonitor/microdeploy/microdeploy-api/0` — 1/1 up (dev)
- `serviceMonitor/microdeploy-prod/microdeploy-api/0` — 2/2 up (prod)

### The MicroDeploy API dashboard
Import `microdeploy-api-dashboard.json` into Grafana (**+** → Import dashboard
→ upload the file → select Prometheus as the data source). Panels:
request rate by handler, p50/p95 latency, pod restarts, pods-up count — all
filterable by a `namespace` dropdown so you can view dev, prod, or both.

### Useful Grafana / Explore queries
| Query | Shows |
|-------|-------|
| `sum by (handler) (rate(http_requests_total{job="microdeploy-api"}[1m]))` | Requests/sec per endpoint |
| `sum(rate(http_requests_total{job="microdeploy-api"}[1m]))` | Total request rate |
| `sum by (pod) (rate(http_requests_total{job="microdeploy-api"}[1m]))` | Load per pod |
| `histogram_quantile(0.95, sum by (le, handler) (rate(http_request_duration_highr_seconds_bucket{job="microdeploy-api"}[5m])))` | p95 latency per endpoint |

Note the metric name: `http_request_duration_highr_seconds_bucket`
(`highr` = high-resolution buckets) — not `http_request_duration_seconds_bucket`.
Confirmed directly against the running cluster; using the wrong name returns
no data.

### View logs in Grafana (Loki)
1. Go to Explore → switch datasource to **Loki**
2. All dev app logs: `{namespace="microdeploy"}`
3. All prod app logs: `{namespace="microdeploy-prod"}`
4. API logs only (either env): `{namespace="microdeploy", container="api"}`

---

## 5. Troubleshooting

### Pod won't start — CrashLoopBackOff
```powershell
kubectl logs -n microdeploy deployment/microdeploy-api          # dev
kubectl logs -n microdeploy-prod deployment/microdeploy-api     # prod
kubectl describe pod -n microdeploy -l app=microdeploy-api
```

### ImagePullBackOff
Check what tag the Deployment is actually trying to pull and whether it
exists in the registry:
```powershell
kubectl describe pod -n microdeploy-prod -l app=microdeploy-api | Select-String "Image"
```
Check events at the bottom of `kubectl describe pod` output — `not found`
means the tag was never built/pushed (e.g. prod pointed at a version tag
that doesn't exist yet); a network-looking error is usually transient.

### Application stuck OutOfSync between two apps that shouldn't collide
```powershell
kubectl describe application <name> -n argocd
```
Look for `SharedResourceWarning` in the Conditions section — this means two
ArgoCD Applications both believe they own the same live object (same name,
same namespace). This should not happen between `api-dev` and `api-prod`
since they're in separate namespaces; if it does, check nothing else
(an old hand-written Application, a leftover manifest) is also targeting
that namespace.

### Application stuck on `Unknown` sync status
Usually means the `targetRevision` (a branch or tag) can't be resolved —
most commonly because a referenced git tag doesn't exist yet. Create/push
the tag, then force a refresh:
```powershell
kubectl annotate application api-prod -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

### git push rejected ("fetch first")
CI's `update-gitops` job commits to `main` independently — if it ran while
you were working locally, your local branch and `origin/main` have diverged.
```powershell
git pull --rebase origin main
git push
```

### API can't connect to database
```powershell
kubectl get pods -n microdeploy -l app=microdeploy-db
kubectl logs -n microdeploy deployment/microdeploy-db
kubectl get configmap microdeploy-config -n microdeploy -o yaml
```

### Prometheus not scraping the API
```powershell
kubectl get svc microdeploy-api -n microdeploy -o yaml | Select-String "labels" -Context 0,3
kubectl get servicemonitor -n microdeploy
kubectl rollout restart deployment/monitoring-kube-prometheus-operator -n monitoring
```

### Grafana shows no data
1. Check Prometheus targets: http://localhost:9090/targets
2. If target is DOWN, check the service label (must have `app: microdeploy-api`)
3. If target is UP but Grafana is empty, check the time range and the
   dashboard's `namespace` filter (it may be scoped to one environment only)
4. Generate traffic and wait ~1 minute for data to appear — a route with
   zero traffic produces no time series at all, not a zero value

### Terraform apply fails
```powershell
terraform init -upgrade
kubectl get nodes
terraform refresh
```

---

## 6. CI/CD Pipeline

The pipeline runs automatically on every push to `main`.

### Pipeline stages
1. **test-and-lint** — ruff lint + pytest for both services
2. **build-scan-push** — docker build → trivy scan → push to ghcr.io (on `main` only)
3. **update-gitops** — edits `gitops/manifests/dev/kustomization.yaml` image
   tags to the new commit SHA, commits with `[skip ci]`-equivalent handling,
   pushes back to `main`

This pipeline **only ever touches the dev overlay**. It never writes to
`gitops/manifests/prod/` and never runs `kubectl` — deployment itself is
entirely ArgoCD's job, triggered by the Git commits this pipeline produces.

### Monitor pipeline
GitHub repository → **Actions** tab

### Manual trigger
```bash
git commit --allow-empty -m "trigger: force pipeline run"
git push
```

### After pipeline succeeds
Nothing to run manually — ArgoCD's `api-dev` Application picks up the new
commit on its own. Confirm with:
```powershell
kubectl get application api-dev -n argocd
kubectl get pods -n microdeploy
```