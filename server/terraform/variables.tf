variable "environment" {
  description = "The environment to deploy to (dev, staging, prod)"
}

variable "external_ingress_hostname" {
  description = "External hostname for the ingress"
  type        = string
}

variable "tls_secret_name" {
  description = "Secret where the TLS certificate for ingress is stored"
  type        = string
}

variable "db_offer" {
  description = "Name of the juju offer for mongodb to use for the cross-model relation"
  type        = string
}

variable "nginx_ingress_integrator_charm_whitelist_source_range" {
  description = "Allowed client IP source ranges. The value is a comma separated list of CIDRs."
  type        = string
  default     = ""
}

variable "nginx_ingress_integrator_charm_max_body_size" {
  description = "Max allowed body-size (for file uploads) in megabytes, set to 0 to disable limits."
  type        = number
  default     = 20
}


variable "application_units" {
  description = "Number of units (pods) to start"
  type        = number
  default     = 2
}

variable "max_pool_size" {
  description = "Maximum number of concurrent connections to the database"
  type        = number
  default     = 100
}

locals {
  app_model = "testflinger-${var.environment}"
}
