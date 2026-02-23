module "agent-host" {
  source               = "git::https://github.com/canonical/testflinger.git//agent/terraform?ref=testflinger-agent-host-0.1.0"
  agent_host_name      = "agent-host-test"
  juju_model           = "testflinger-agents"
  config_repo          = "https://github.com/canonical/testflinger.git"
  config_branch        = "main"
  config_dir           = "agent/charms/testflinger-agent-host-charm/tests/integration/data/test01"
  ssh_public_key       = filebase64("id_rsa.pub")
  ssh_private_key      = filebase64("id_rsa")
  override_constraints = "arch=amd64 cores=1 mem=2048M root-disk=10240M root-disk-source=default virt-type=virtual-machine"
}