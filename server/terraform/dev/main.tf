# Testflinger Terraform module
module "testflinger" {
    source     = "../"
    app_name   = "testflinger"
    model_uuid = data.juju_model.testflinger_dev_model.uuid
    units      = 2
    base       = "ubuntu@22.04"
    channel    = "latest/beta"
    config     = {
        external_hostname              = "testflinger.local"
        http_proxy                     = ""
        https_proxy                    = ""
        no_proxy                       = "localhost,127.0.0.1,::1"
        max_pool_size                  = "100"
        jwt_signing_key                = var.jwt_signing_key
        testflinger_secrets_master_key = var.testflinger_secrets_master_key
    }
}

# Data Source for juju model
data "juju_model" "testflinger_dev_model" {
  name = "testflinger-dev"
  owner = "admin"
}

# Nginx Ingress Integrator Terraform resource
resource "juju_application" "ingress" {
  name       = "ingress"
  model_uuid = data.juju_model.testflinger_dev_model.uuid
  trust = true

  charm {
    name    = "nginx-ingress-integrator"
    channel = "latest/stable"
  }

  config = {
    tls-secret-name        = ""
    whitelist-source-range = ""
    max-body-size          = "20"
  }
}

# Juju integration between MongoDB and Testflinger application
resource "juju_integration" "testflinger_database_relation" {
  model_uuid = data.juju_model.testflinger_dev_model.uuid

  application {
    name     = module.testflinger.application.name
    endpoint = "mongodb_client"
  }

  application {
    offer_url = "admin/testflinger-dev-db.mongodb"
    endpoint  = "database"
  }
}

# Juju integration between Ingress and Testflinger application
resource "juju_integration" "testflinger_ingress_relation" {
  model_uuid = data.juju_model.testflinger_dev_model.uuid

  application {
    name = module.testflinger.application.name
  }

  application {
    name = juju_application.ingress.name
  }
}
