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

data "juju_model" "agent-host-model" {
  name = var.juju_model
}

resource "juju_secret" "credentials-secret" {
  model_uuid = data.juju_model.agent-host-model.uuid
  name       = var.credentials_secret_name
  value = {
    client-id = var.credentials_secret_client_id
    secret-key = var.credentials_secret_secret_key
  }
  info = "Juju secret for agent host credentials"
}

resource "juju_access_secret" "credentials-secret-access" {
  model_uuid   = data.juju_model.agent-host-model.uuid
  secret_id    = juju_secret.credentials-secret.secret_id
  applications = [juju_application.testflinger-agent-host.name]
}
