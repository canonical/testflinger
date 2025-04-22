# Juju deployment

Local Juju and charm deployment via [Terraform].

## Set up variables

The agent host charm requires a few variables. When deploying via Terraform,
these can be placed in a `terraform.tfvars` file:

```tf
juju_model = "testflinger-agents"
agent_host_name = "agent-host"

config_repo = "https://..."
config_branch = "main"
config_dir = "lab/agent-host"

ssh_public_key <<-EOT
(sensitive value)
EOT

ssh_private_key <<-EOT
(sensitive value)
EOT
```

> [!TIP]
> To generate the SSH key, use (for example): `ssh-keygen -t rsa -f id_rsa`.

> [!NOTE]
> The agent host expects to pull configurations from a git repository. Make sure that the your URL includes any tokens needed to access the repository (e.g., FPAT).

## Set up a Juju environment

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

## Initialize project's terraform

Now that everything has been set up, you can initialize the project's terraform.

In the terraform directory on your host machine, run:

```shell
multipass exec testflinger-agents-juju -- terraform init
```

## Deploy everything

In the terraform directory on your host machine, run:

```shell
multipass exec testflinger-agents-juju -- terraform apply -auto-approve
```

Then wait for the deployment to settle and all the statuses to become active.
You can watch the statuses via:

```shell
multipass exec testflinger-agents-juju -- juju status --storage --relations --watch 5s
```

## Teardown

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

[Terraform]: https://developer.hashicorp.com/terraform
[Multipass]: https://canonical.com/multipass
