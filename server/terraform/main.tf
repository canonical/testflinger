resource "juju_application" "testflinger" {
  name        = var.app_name
  model_uuid  = var.model_uuid
  constraints = var.constraints
  units       = var.units
  config      = var.config

  charm {
    name     = "testflinger-k8s"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}
