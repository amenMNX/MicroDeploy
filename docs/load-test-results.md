# Load Test Results

## Test Setup

| Parameter | Value |
|-----------|-------|
| Tool | PowerShell `Invoke-WebRequest` loop |
| Target | `http://localhost:8081/tasks` (port-forwarded to Kubernetes) |
| Request interval | 200ms (~5 req/s per terminal) |
| Duration | ~10 minutes |
| API replicas | 2 |
| Environment | Rancher Desktop (local Kubernetes) |

## Test Command Used

```powershell
while ($true) {
    Invoke-WebRequest -Uri "http://localhost:8081/tasks" -UseBasicParsing | Out-Null
    Invoke-WebRequest -Uri "http://localhost:8081/" -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 200
}
```

---

## Results

### Request Rate by Endpoint

Observed via Grafana query:
```promql
sum by (handler) (rate(http_requests_total{job="microdeploy-api"}[1m]))
```

| Endpoint | Observed Rate | Source |
|----------|--------------|--------|
| `/tasks` | ~11.1 req/s | Load test loop |
| `/health` | ~0.6 req/s | Kubernetes liveness/readiness probes |
| `/metrics` | ~0.13 req/s | Prometheus scraping (every 15s) |
| `/` | ~3.5 req/s | Load test loop |

### Total Request Rate

Observed via:
```promql
sum(rate(http_requests_total{job="microdeploy-api"}[1m]))
```

- Peak: **~15 req/s** across both pods
- Baseline (no load): **~0.75 req/s** (probes + Prometheus scrape only)

### Load Distribution by Pod

Observed via:
```promql
sum by (pod) (rate(http_requests_total{job="microdeploy-api"}[1m]))
```

| Pod | Rate |
|-----|------|
| microdeploy-api-6c5468bf8c-cxpz9 | ~14.9 req/s |
| microdeploy-api-6c5468bf8c-wj7hd | ~0.35 req/s |

**Note:** The uneven distribution is expected in this setup. `kubectl port-forward`
connects directly to a single pod rather than going through the Service load balancer.
In a production environment with an external LoadBalancer or Ingress, traffic would
be distributed evenly across both replicas using round-robin by default.

---

## Observations

### What Worked Well
- The API handled sustained load (~15 req/s) with no errors or crashes
- Kubernetes readiness and liveness probes ran reliably throughout (`/health` at ~0.6 req/s)
- Prometheus scraped metrics continuously without gaps
- Both pods remained in `Running` state throughout the test
- The worker processed tasks in the background without affecting API performance

### Prometheus Scraping Confirmed
- Both API pods were scraped successfully (`2/2 up` in Prometheus targets)
- Scrape latency: 2ms (pod 1), 6ms (pod 2) — well within the 15s interval

### Improvement Opportunities
- Add a proper load balancer (e.g., Ingress with NGINX) to enable real traffic distribution across replicas
- Add database connection pooling (e.g., PgBouncer) for higher concurrency
- Add Horizontal Pod Autoscaler (HPA) to scale replicas automatically under load
- Implement response time SLOs and configure Alertmanager to fire when p95 latency exceeds threshold

---

## Grafana Dashboard Queries (Reference)

```promql
# Requests per second by endpoint
sum by (handler) (rate(http_requests_total{job="microdeploy-api"}[1m]))

# Total request rate
sum(rate(http_requests_total{job="microdeploy-api"}[1m]))

# Per-pod request rate (load balancing visibility)
sum by (pod) (rate(http_requests_total{job="microdeploy-api"}[1m]))

# 95th percentile response latency
histogram_quantile(0.95, sum by (le, handler) (rate(http_request_duration_seconds_bucket{job="microdeploy-api"}[1m])))
```