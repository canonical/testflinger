# Contributing to Testflinger Terraform modules

This document outlines contribution guidelines specific to the Testflinger Agent Host Terraform module.

To learn more about the general contribution guidelines for the Testflinger project, refer to the [Testflinger contribution guide](../../CONTRIBUTING.md).

## Pull Requests

Any change to the terraform modules should be semantically versioned, for automation to automatically tag your commits,
you should consider the following patterns:
- `breaking(terraform-agent):` -  Creates a major release
- `feat(terraform-agent):` Creates a minor release

By default, any commit without the above patterns will create a patch version bump. Refer to [Terraform versioning guide][versioning-guide] to understand more about semantic versioning Terraform modules.

## Testflinger Agent Host Terraform Deployment

The following instructions are meant to provide developers a guide on how to
deploy a Testflinger Agent Host by using [Terraform].

### Set up a Juju environment

It is recommended to install the pre-requisites on a VM rather than your host
machine. To do so, first install [Multipass]:

```shell
sudo snap install multipass
```

Then launch a new VM instance (this may take a while):

```shell
multipass launch noble --disk 50G --memory 4G --cpus 2 --name testflinger-agents-juju --mount /path/to/testflinger:/home/ubuntu/testflinger --cloud-init /path/to/testflinger/agent/terraform/cloud-init.yaml --timeout 1200
```

Feel free to increase the storage, memory, CPU, or VM name.

> [!NOTE]
> The initialization may time out. That's fine as long as the setup actually completed. You can tell that the setup completed by checking if the Juju models were created.

Check that the models were created:

```shell
multipass exec testflinger-agents-juju -- juju models
```

### Initialize project's terraform

Now that everything has been set up, you can initialize the project's terraform.
The following guide setups a higher-level module to configure the Testflinger
Agent Host Charm deployment.

Change your directory on your host machine to the terraform dev directory:

```shell
cd /path/to/testflinger/agent/terraform/dev
```

Then run:

```shell
multipass exec testflinger-agents-juju -- terraform init
```

### Set up variables

Refer to the [README](README.md#usage) for the full list of required variables. 

`terraform/dev` directory contains the required terraform files for deployment, modify them accordingly
with the necessary variables such as ssh keys. 

> [!TIP]
> To generate the SSH key, use (for example): `ssh-keygen -t rsa -f id_rsa`.

> [!NOTE]
> The agent host expects to pull configurations from a git repository. Make sure
> that your URL includes any tokens needed to access the repository (e.g., FPAT).


### Deploy

In the terraform directory on your host machine, run:

```shell
multipass exec testflinger-agents-juju -- terraform apply -auto-approve
```

Then wait for the deployment to settle and all the statuses to become active.
You can watch the statuses via:

```shell
multipass exec testflinger-agents-juju -- juju status --storage --relations --watch 5s
```

### Teardown

To take everything down, you can start with terraform:

```shell
multipass exec testflinger-agents-juju -- terraform destroy -auto-approve
```

The above step can take a while and may even get stuck with some applications
in error state. You can watch it through:

```bash
multipass exec testflinger-agents-juju -- juju status --storage --relations --watch 5s
```

Once everything is down and the juju model has been deleted you can stop the
multipass VM:

```bash
multipass stop testflinger-agents-juju
```

Optionally, delete the VM:

```bash
multipass delete --purge testflinger-agents-juju
```

[Multipass]: https://canonical.com/multipass
[Terraform]: https://developer.hashicorp.com/terraform
[versioning-guide]: https://developer.hashicorp.com/terraform/plugin/best-practices/versioning