resource "juju_application" "testflinger" {
  name  = "testflinger"
  model = local.app_model

  units = 2

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
  model = local.app_model
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
  model = local.app_model

  application {
    name = juju_application.testflinger.name
  }

  application {
    offer_url = var.db_offer
  }
}

resource "juju_integration" "testflinger-ingress-relation" {
  model = local.app_model

  application {
    name     = juju_application.testflinger.name
  }

  application {
    name     = juju_application.ingress.name
  }
}


