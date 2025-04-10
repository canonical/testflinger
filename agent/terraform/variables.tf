variable "juju_model" {
  type        = string
  description = "Name of the Juju model"
}

variable "channel" {
  description = "Channel to use for the charm"
  type        = string
  default     = "latest/stable"
}

variable "revision" {
  description = "Revision of the charm to use"
  type        = number
  nullable    = true
  default     = null
}

variable "agent_host_name" {
  type        = string
  description = "Name of the agent host juju application"
}

variable "agent_host_cores" {
  type        = number
  description = "Number of cpu cores to use for the agent host"
  default     = 4
}

variable "agent_host_mem" {
  type        = string
  description = "Amount of RAM to use for the agent host"
  default     = "32768M"
}

variable "agent_host_storage" {
  type        = string
  description = "Storage size for the agent host"
  default     = "1048576M"
}

variable "override_constraints" {
  type        = string
  description = "Use if you need to override the constraints built with the other agent_host_* vars"
  default     = ""
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
  sensitive   = true
  type        = string
  description = "base64 encoded ssh public key to use on the agent host"
}

variable "ssh_private_key" {
  sensitive   = true
  type        = string
  description = "base64 encoded ssh private key to use on the agent host"
}
