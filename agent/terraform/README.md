# Terraform module for Testflinger Agent Host

This is a Terraform module facilitating the deployment of the Testflinger Agent Host charm,
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
| `app_name` | string | Name of the agent host juju application | True |
| `base` | string | Operating system base to use for the agent host charm | False |
| `channel` | string | Channel to use for the charm | False |
| `config` | map(string) | Map of charm config options | False |
| `config_repo` | string | Repository URL for the agent configs on this agent host (sensitive) | True |
| `constraints` | string | Constraints to use for the agent host application | False |
| `model_uuid` | string | UUID of the Juju model to deploy into | True |
| `revision` | number | Revision of the charm to use | False |
| `ssh_private_key` | string | base64 encoded ssh private key to use on the agent host (sensitive) | True |
| `ssh_public_key` | string | base64 encoded ssh public key to use on the agent host (sensitive) | True |
| `units` | number | Number of units for the agent host application | False |

The following charm config options should be passed via the `config` map:

| Key | Description |
| - | - |
| `config-branch` | Repository branch for the agent configs |
| `config-dir` | Directory within the config repo containing the charm configuration |
| `credentials-secret` | Juju secret URI containing the credentials for authenticating with the Testflinger server |
| `testflinger-server` | Testflinger server URL for the agent host to connect to |

### Outputs

| Name | Type | Description |
| - | - | - |
| `application` | object | The deployed application object |
| `provides` | map(string) | Map of provided integration endpoints |

## Usage
This module is intended to be used as part of a higher-level module.
When defining one, users should ensure that Terraform is aware of the `model_uuid` dependency of the charm module.

### Define a `data` source

Define a `data` source and pass to the `model_uuid` input a reference to the `data.juju_model` resource's name. 
This will enable Terraform to look for a `model_uuid` resource with a name attribute equal to the one provided, 
and apply only if this is present. Otherwise, it will fail before applying anything.

```hcl
data "juju_model" "agent-host" {
  name = "<model-name>"
}
```

### Define a secret resource

Define a `juju_secret` resource with the required fields and make sure to grant access to the Juju application.

```hcl
resource "juju_secret" "credentials-secret" {
  model_uuid = data.juju_model.agent-host.uuid
  name       = <secret name>
  value = {
    client-id  = <client-id>
    secret-key = <secret-key>
  }
  info = "Juju secret for agent host credentials"
}
```

```hcl
resource "juju_access_secret" "credentials-secret-access" {
  model_uuid   = data.juju_model.agent-host.uuid
  secret_id    = juju_secret.credentials-secret.secret_id
  applications = [module.testflinger-agent-host.application.name]
}
```

### Create module

Then call the module:

```hcl
module "testflinger-agent-host" {
  source          = "git::https://github.com/canonical/testflinger.git//agent/terraform?ref=<tag>"
  model_uuid      = data.juju_model.agent-host.uuid
  app_name        = "<name>"
  config_repo     = "<repo-url>"
  ssh_public_key  = filebase64("id_rsa.pub")
  ssh_private_key = filebase64("id_rsa")
  config = {
    config-branch      = "main"
    config-dir         = "<path>"
    testflinger-server = "https://testflinger.canonical.com"
    credentials-secret = "secret:${juju_secret.credentials-secret.secret_id}"
  }
}
```

[juju-provider]: https://github.com/juju/terraform-provider-juju/
[juju-provider-docs]: https://registry.terraform.io/providers/juju/juju/latest/docs
