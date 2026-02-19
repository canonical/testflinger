resource "juju_application" "testflinger-agent-host" {
  name        = var.agent_host_name
  model       = var.juju_model
  constraints = local.agent_host_constraints

  units = 1

  charm {
    name     = "testflinger-agent-host"
    base     = "ubuntu@22.04"
    channel  = var.channel
    revision = var.revision
  }

  config = {
    ssh-public-key  = var.ssh_public_key
    ssh-private-key = var.ssh_private_key
    config-repo     = var.config_repo
    config-branch   = var.config_branch
    config-dir      = var.config_dir
    testflinger-server = var.testflinger_server
    credentials-secret = juju_secret.credentials-secret.secret_id
  }
}

resource "juju_secret" "credentials-secret" {
  model_uuid = juju_model.development.uuid
  name       = var.credentials_secret_name
  value = {
    client-id = var.credentials_secret_client_id
    secret-key = var.credentials_secret_secret_key
  }
  info = "Juju secret for agent host credentials"
}
