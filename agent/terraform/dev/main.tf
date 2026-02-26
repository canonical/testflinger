module "agent-host" {
  source               = "git::https://github.com/canonical/testflinger.git//agent/terraform?ref=feat/update-terraform"
  app_name             = "agent-host-test"
  model_uuid           = data.juju_model.agent-host-model.uuid
  constraints          = "arch=amd64 cores=1 mem=2048M root-disk=10240M root-disk-source=default virt-type=virtual-machine"
  units                = 1
  base                 = "ubuntu@22.04"
  channel              = "latest/beta"
  revision             = 84
  config_repo          = "https://github.com/canonical/testflinger.git"
  ssh_public_key       = filebase64("id_rsa.pub")
  ssh_private_key      = filebase64("id_rsa")
  config = {
    "config-branch"      = "main"
    "config-dir"         = "agent/charms/testflinger-agent-host-charm/tests/integration/data/test01"
    "credentials-secret" = "secret:${juju_secret.credentials-secret.secret_id}"
    "testflinger-server" = "https://testflinger.canonical.com"
  }
}

data "juju_model" "agent-host-model" {
  name = "testflinger-agents"
  owner = "admin"
}

resource "juju_secret" "credentials-secret" {
  model_uuid = data.juju_model.agent-host-model.uuid
  name       = "test-credentials"
  value = {
    client-id  = "fake-client-id"
    secret-key = "fake-secret-key"
  }
  info = "Juju secret for agent host credentials"
}

resource "juju_access_secret" "credentials-secret-access" {
  model_uuid   = data.juju_model.agent-host-model.uuid
  secret_id    = juju_secret.credentials-secret.secret_id
  applications = [module.agent-host.application.name]
}
