# Terraform module for Testflinger Server

This is a Terraform module facilitating the deployment of the Testflinger Server charm,
using the [Terraform Juju provider][juju-provider]. For more information, refer
to the provider [documentation][juju-provider-docs].

## Requirements

This module requires a Juju model UUID to be available. Refer to the [usage section](#usage)
below for more details.

## API

### Inputs

The module offers the following configurable inputs:

| Name | Type | Description | Required |
| - | - | - | - |
| `app_name` | string | Name of the Testflinger server application | True |
| `base` | string | Operating system base to use for the Testflinger server charm | False |
| `channel` | string | Channel to use for the charm | False |
| `config` | map(string) | Map of charm config options | False |
| `constraints` | string | Constraints to use for the Testflinger server application | False |
| `model_uuid` | string | UUID of the Juju model to deploy into | True |
| `revision` | number | Revision of the charm to use | False |
| `units` | number | Number of units for the Testflinger server application | False |


### Outputs

| Name | Type | Description |
| - | - | - |
| `application` | object | The deployed application object |
| `provides` | map(string) | Map of provides integration endpoints |
| `requires` | map(string) | Map of requires integration endpoints |

## Usage
This module is intended to be used as part of a higher-level module.
When defining one, users should ensure that Terraform is aware of the `model_uuid` dependency of the charm module.

### Define a `data` source

Define a `data` source and pass to the `model_uuid` input a reference to the `data.juju_model` resource's name. 
This will enable Terraform to look for a `model_uuid` resource with a name attribute equal to the one provided, 
and apply only if this is present. Otherwise, it will fail before applying anything.

```hcl
data "juju_model" "testflinger_dev" {
  name = "<model-name>"
}
```

### Create module

Then call the module:

```hcl
module "testflinger" {
  source          = "git::https://github.com/canonical/testflinger.git//server/terraform?ref=<tag>"
  model_uuid      = data.juju_model.testflinger_dev.uuid
  app_name        = "<name>"
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
```

[juju-provider]: https://github.com/juju/terraform-provider-juju/
[juju-provider-docs]: https://registry.terraform.io/providers/juju/juju/latest/docs