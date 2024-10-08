variable "juju_model" {
  type        = string
  description = "Name of the Juju model"
}

variable "agent_host_name" {
  type        = string
  description = "Name of the agent host juju application"
}

variable "config_repo" {
  type        = string
  description = "Repository URL for the agent configs on this agent host"
}

variable "config_branch" {
  type        = string
  description = "Repository branch for the agent configs"
}

variable "config_dir" {
  type        = string
  description = "Directory within the config repo containing the charm configuration"
}

variable "ssh_public_key" {
  type        = string
  description = "base64 encoded ssh public key to use on the agent host"
}

variable "ssh_private_key" {
  type        = string
  description = "base64 encoded ssh private key to use on the agent host"
}

