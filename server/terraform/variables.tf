variable "app_name" {
  description = "Name of the Testflinger application to deploy"
  type        = string
  default     = "testflinger"
}

variable "base" {
  description = "Operating system base to use for the Testflinger Server charm"
  type        = string
  nullable    = true
  default     = null
}

variable "channel" {
  description = "Channel to use for the Testflinger charm."
  type        = string
  default     = "latest/stable"
}

variable "config" {
  description = "Map of charm config options"
  type        = map(string)
  default     = {}
}

variable "constraints" {
  description = "Constraints to apply to the Testflinger application"
  type        = string
  nullable    = true
  default     = null
}

variable "model_uuid" {
  description = "UUID of the Juju model to deploy into"
  type        = string
}

variable "revision" {
  description = "Revision of the charm to use"
  type        = number
  nullable    = true
  default     = null
}

variable "units" {
  description = "Number of units for the server application"
  type        = number
  default     = 1
}
