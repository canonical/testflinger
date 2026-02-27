output "application" {
  description = "The deployed application"
  value       = juju_application.testflinger_agent_host
}

output "provides" {
  description = "Map of provided integration endpoints"
  value = {
    cos_agent = "cos-agent"
  }
}
