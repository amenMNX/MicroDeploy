# Load Test Results

> **Note:** This test was run against the `microdeploy` (dev) namespace,
> before the dev/prod namespace split. The results below are unchanged from
> the original run. A corresponding prod-specific load test has not yet been
> performed — see "Not Yet Tested" at the end of this document.

## Test Setup

| Parameter | Value |
|-----------|-------|
| Tool | PowerShell `Invoke-WebRequest` loop |
| Target | `http://localhost:8081/tasks` (port-forwarded to Kubernetes) |
| Request interval | 200ms (~5 req/s per terminal) |
| Duration | ~10 minutes |
| API replicas | 2 |
| Environment | Rancher Desktop (local Kubernetes), namespace `microdeploy` |

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

## Not Yet Tested

The following are relevant now that the project has moved to a dev/prod
split with GitOps deployment, and have **not** been measured — this is a
list of real gaps, not results:

- **Prod-specific load test.** Prod runs 2 replicas with its own database;
  it has never been load tested directly. The numbers above are dev-only.
- **Behavior during an ArgoCD sync.** Whether in-flight requests are
  dropped or queued when a rolling update is triggered mid-load has not
  been observed.
- **Behavior under the shared-nothing dev/prod split vs. the old
  shared-namespace setup this test predates** — i.e. whether separating
  the databases changed latency or resource usage at all. Unlikely to
  matter, but unverified.

---

## Grafana Dashboard Queries (Reference)

**Corrected from the original version of this document** — the latency
query below previously referenced `http_request_duration_seconds_bucket`,
which is not the actual metric name this API exposes and would return no
data. Confirmed directly against the running cluster: the real metric is
`http_request_duration_highr_seconds_bucket` (`highr` = high-resolution
buckets).

```promql
# Requests per second by endpoint
sum by (handler) (rate(http_requests_total{job="microdeploy-api"}[1m]))

# Total request rate
sum(rate(http_requests_total{job="microdeploy-api"}[1m]))

# Per-pod request rate (load balancing visibility)
sum by (pod) (rate(http_requests_total{job="microdeploy-api"}[1m]))

# 95th percentile response latency (corrected metric name)
histogram_quantile(0.95, sum by (le, handler) (rate(http_request_duration_highr_seconds_bucket{job="microdeploy-api"}[1m])))

# To scope any of the above to one environment, add a namespace filter, e.g.:
sum by (handler) (rate(http_requests_total{job="microdeploy-api", namespace="microdeploy-prod"}[1m]))
```