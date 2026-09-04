resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "helm_release" "prometheus_stack" {
  name             = "monitoring"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = kubernetes_namespace.monitoring.metadata[0].name
  timeout          = 900
  cleanup_on_fail  = true
  atomic           = true

  set_sensitive {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }

  set {
    name  = "grafana.serviceMonitor.enabled"
    value = "false"
  }

  depends_on = [kubernetes_namespace.monitoring]
}

resource "helm_release" "loki_stack" {
  name             = "loki-stack"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "loki-stack"
  namespace        = kubernetes_namespace.monitoring.metadata[0].name
  timeout          = 300
  cleanup_on_fail  = true
  atomic           = true

  set {
    name  = "promtail.enabled"
    value = "true"
  }

  set {
    name  = "grafana.enabled"
    value = "false"
  }

  set {
    name  = "prometheus.enabled"
    value = "false"
  }

  depends_on = [kubernetes_namespace.monitoring]
}
