resource "juju_application" "testflinger-agent-host" {
  name        = var.agent_host_name
  model       = var.juju_model
  constraints = local.agent_host_constraints

  units = 1

  charm {
    name    = "testflinger-agent-host"
    base    = "ubuntu@22.04"
    channel = "latest/beta"
  }

  config = {
    ssh-public-key  = var.ssh_public_key
    ssh-private-key = var.ssh_private_key
    config-repo     = var.config_repo
    config-branch   = var.config_branch
    config-dir      = var.config_dir
  }
}

