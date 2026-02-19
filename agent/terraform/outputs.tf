output "app_name" {
  description = "Name of the deployed application"
  value       = juju_application.testflinger-agent-host.name
}