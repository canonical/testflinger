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

locals {
  app_model = "testflinger-${var.environment}"
}
