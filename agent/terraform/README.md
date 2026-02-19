# Terraform module for Testflinger Agent Host

This is a Terraform module facilitating the deployment of the Testflinger Agent Host charm,
using the [Terraform Juju provider][juju-provider]. For more information, refer
to the provider [documentation][juju-provider-docs].

## Requirements
This module requires a `juju` model to be available. Refer to the [usage section](#usage) below for more details.

## API

### Inputs
The module offers the following configurable inputs:

| Name | Type | Description | Required |
| - | - | - | - |
| `juju_model`| string | Name of the Juju model | True |
| `channel`| string | Channel to use for the charm | False |
| `revision`| number | Revision of the charm to use (minimum: 82) | False |
| `agent_host_name`| string | Name of the agent host juju application | True |
| `override_constraints`| string | Use if you need to override the constraints built with the agent_host_* vars | False |
| `config_repo`| string | Repository URL for the agent configs on this agent host | True |
| `config_branch`| string | Repository branch for the agent configs | False |
| `config_dir`| string | Directory within the config repo containing the charm configuration | True |
| `ssh_public_key`| string | base64 encoded ssh public key to use on the agent host | True |
| `ssh_private_key`| string | base64 encoded ssh private key to use on the agent host | True |
| `testflinger_server`| string | Testflinger server URL for the agent host to connect to | False |
| `credentials_secret_name`| string | Name of the Juju secret for the agent host credentials | True |
| `credentials_secret_client_id`| string | Client ID for the Juju secret for the agent host credentials | True |
| `credentials_secret_secret_key`| string | Secret key for the Juju secret for the agent host credentials| True |

### Outputs

| Name     | Type   | Description                      |
| -------- | ------ | -------------------------------- |
| app_name | string | Name of the deployed application |

## Usage

### Basic Usage

Users should ensure that Terraform is aware of all the required variables including 
the `juju_model` dependency of the charm module. Given the total amount of required 
variables, it is recommended to use a `.tfvars` file.

1. Create a `.tfvars` file with at least the required values:

```hcl
juju_model                     = "<model>"
agent_host_name                = "<name>"
config_repo                    = "<repo-url>"
config_dir                     = "<path>"
ssh_public_key                 = "<base64-key>"
ssh_private_key                = "<base64-key>"
credentials_secret_name        = "<secret-name>"
credentials_secret_client_id   = "<client-id>"
credentials_secret_secret_key  = "<secret-key>"
revision                       = 82
```

2. Deploy with:

```shell
terraform apply -var-file="<name>.tfvars"
```

[juju-provider]: https://github.com/juju/terraform-provider-juju/
[juju-provider-docs]: https://registry.terraform.io/providers/juju/juju/latest/docs