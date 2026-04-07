output "application" {
  description = "The deployed application"
  value       = juju_application.testflinger
}

output "provides" {
  description = "Map of provided integration endpoints"
  value = {
    grafana_dashboard = "grafana-dashboard"
    metrics_endpoint  = "metrics-endpoint"
  }
}

output "requires" {
  description = "Map of requires integration endpoints"
  value = {
    mongodb_client   = "mongodb_client"
    mongodb_keyvault = "mongodb_keyvault"
    nginx_route      = "nginx-route"
    traefik_route    = "traefik-route"
  }
}
