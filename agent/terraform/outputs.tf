output "application" {
  description = "The deployed application"
  value       = juju_application.testflinger-agent-host
}

output "provides" {
  description = "Map of provided integration endpoints"
  value = {
    cos_agent = "cos-agent"
  }
}
