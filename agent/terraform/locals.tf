locals {
  agent_host_constraints = coalesce(var.override_constraints, "arch=amd64 cores=${var.agent_host_cores} mem=${var.agent_host_mem} root-disk=${var.agent_host_storage} root-disk-source=remote virt-type=virtual-machine")
}
