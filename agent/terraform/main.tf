resource "juju_application" "testflinger-agent-host" {
  name        = var.app_name
  model_uuid  = var.model_uuid
  constraints = var.constraints
  units       = var.units
  config      = merge(var.config, {
    ssh-public-key  = var.ssh_public_key
    ssh-private-key = var.ssh_private_key
    config-repo     = var.config_repo
  })

  charm {
    name     = "testflinger-agent-host"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}
