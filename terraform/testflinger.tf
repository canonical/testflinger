terraform {
  required_providers {
    juju = {
      version = "~> 0.7.0"
      source  = "juju/juju"
    }
  }
}

provider "juju" {}


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

resource "juju_model" "testflinger_model" {
  name = "testflinger-${var.environment}"
}

resource "juju_application" "testflinger" {
  name  = "testflinger"
  model = juju_model.testflinger_model.name

  charm {
    name    = "testflinger-k8s"
    series  = "jammy"
    channel = "edge"
  }

  config = {
    external_hostname = var.external_ingress_hostname
  }
}

resource "juju_application" "ingress" {
  name  = "ingress"
  model = juju_model.testflinger_model.name
  trust = true

  charm {
    name    = "nginx-ingress-integrator"
    channel = "stable"
  }

  config = {
    tls-secret-name = var.tls_secret_name
  }
}

resource "juju_integration" "testflinger-database-relation" {
  model = juju_model.testflinger_model.name

  application {
    name     = juju_application.testflinger.name
  }

  application {
    name     = "mongodb-k8s"
  }
}

resource "juju_integration" "testflinger-ingress-relation" {
  model = juju_model.testflinger_model.name

  application {
    name     = juju_application.testflinger.name
  }

  application {
    name     = juju_application.ingress.name
  }
}


