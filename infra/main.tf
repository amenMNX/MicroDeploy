# The monitoring namespace (infrastructure, managed by Terraform)
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

# Prometheus + Grafana + Alertmanager, installed as one Helm chart
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
}