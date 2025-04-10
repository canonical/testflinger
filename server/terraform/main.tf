resource "juju_application" "testflinger" {
  name  = "testflinger"
  model = local.app_model

  units = var.application_units

  charm {
    name     = "testflinger-k8s"
    base     = "ubuntu@22.04"
    channel  = local.channel
    revision = var.revision
  }

  config = {
    external_hostname = var.external_ingress_hostname
    max_pool_size     = var.max_pool_size
    jwt_signing_key   = var.jwt_signing_key
  }
}

resource "juju_application" "ingress" {
  name  = "ingress"
  model = local.app_model
  trust = true

  charm {
    name    = "nginx-ingress-integrator"
    channel = "latest/stable"
  }

  config = {
    tls-secret-name        = var.tls_secret_name
    whitelist-source-range = var.nginx_ingress_integrator_charm_whitelist_source_range
    max-body-size          = var.nginx_ingress_integrator_charm_max_body_size
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
    name = juju_application.testflinger.name
  }

  application {
    name = juju_application.ingress.name
  }
}


