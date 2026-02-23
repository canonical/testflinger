variable "app_name" {
  type        = string
  description = "Name of the agent host juju application"
}

variable "base" {
  description = "Operating system base to use for the agent host charm"
  type        = string
  default     = null
}

variable "channel" {
  description = "Channel to use for the agent host charm"
  type        = string
  default     = "latest/stable"
}

variable "config" {
  type        = map(string)
  default     = {}
  description = "Map of charm config options"
}

variable "config_repo" {
  sensitive   = true
  type        = string
  description = "Repository URL for the agent configs on this agent host"
}

variable "constraints" {
  type        = string
  nullable    = true
  default     = null
  description = "Constraints to use for the agent host application"
}

variable "model_uuid" {
  type        = string
  description = "UUID of the Juju model to deploy into"
}

variable "revision" {
  description = "Revision of the charm to use"
  type        = number
  nullable    = true
  default     = null
}

variable "ssh_private_key" {
  sensitive   = true
  type        = string
  description = "base64 encoded ssh private key to use on the agent host"
}

variable "ssh_public_key" {
  sensitive   = true
  type        = string
  description = "base64 encoded ssh public key to use on the agent host"
}

variable "units" {
  type        = number
  description = "Number of units for the agent host application"
  default     = 1
}
