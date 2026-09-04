# The monitoring namespace (infrastructure, managed by Terraform)
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }# Pr# Prometheus + Grafana + Alertmanager, installed as one Helm chart
# Also configures Grafana to use Loki as a datasource automatically
resource "helm_release" "prometheus_stack" {
  name       = "monitoring"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  timeout = 900

  set {
    name  = "grafana.adminPassword"
    value = "admin123"
  }

  # Wire Loki into Grafana as a datasource automatically
  set {
    name  = "grafana.additionalDataSources[0].name"
    value = "Loki"
  }

  set {
    name  = "grafana.additionalDataSources[0].type"
    value = "loki"
  }

  set {
    name  = "grafana.additionalDataSources[0].url"
    value = "http://loki-stack.monitoring.svc.cluster.local:3100"
  }

  set {
    name  = "grafana.additionalDataSources[0].access"
    value = "proxy"
  }

  set {
    name  = "grafana.additionalDataSources[0].isDefault"
    value = "false"
  }

  # Prometheus stack must exist before Loki datasource is meaningful
  depends_on = [kubernetes_namespace.monitoring]
}

# Loki + Promtail, installed as one Helm chart
# Promtail runs as a DaemonSet and ships logs from every pod to Loki
resource "helm_release" "loki_stack" {
  name       = "loki-stack"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  timeout = 300

  # Enable Promtail (the log collector agent)
  set {
    name  = "promtail.enabled"
    value = "true"
  }

  # Disable Grafana inside loki-stack (we already have it from prometheus_stack)
  set {
    name  = "grafana.enabled"
    value = "false"
  }

  # Disable Prometheus inside loki-stack (we already have it)
  set {
    name  = "prometheus.enabled"
    value = "false"
  }

  # Loki must be deployed after the namespace exists
alue = "false"
  }

  # Loki must be deployed after the namespace exists
  depends_on = [kubernetes_namespace.monitoring]
}
