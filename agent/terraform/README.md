# Deploying with Terraform + Juju

This Terraform module can be used for deploying the Testflinger agent
host on a physical or virtual machine model using Juju.

## Deploying an Environment

This terraform module assume that the Juju model you want to deploy
to has already been created.

1. First, create the model

    ```
        $ juju add-model agent-host-1
    ```

2. Create ssh keys to use on the agent host

    ```
        $ ssh-keygen -t rsa -f mykey
    ```

3. Create a git repo with the Testflinger configs

    If you have more than one agent host to deploy, create a separate directory
    for each of them in this repo. Then create a separate directory for each
    agent in the agent host directory where they reside. For example:

    ```
    /agent-host-1
    -/agent-101
      -testflinger-agent.yaml
      -default.conf
    -/agent-102
      -testflinger-agent.yaml
      -default.conf
    /agent-host-2
    ...
    ```

4. Create a main.tf which specifies the required parameters for this module

    ```
    terraform {
      required_providers {
        juju = {
          version = "~> 0.13.0"
          source  = "juju/juju"
        }
      }
    }

    provider "juju" {}

    module "lab1" {
      source = "/path/to/this/module"
      agent_host_name = "agent-host-1"
      juju_model = "agent-host-1"
      config_repo = "https://github.com/path_to/config_repo.git"
      config_branch = "main"
      config_dir = "agent-host-1"
      ssh_public_key = filebase64("mykey.pub")
      ssh_private_key = filebase64("mykey")
    }
    ```

5. Initialize terraform and apply
    ```
        $ terraform init
        $ terraform apply
    ```

