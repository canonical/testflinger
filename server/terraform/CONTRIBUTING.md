# Contributing to Testflinger Terraform modules

This document outlines contribution guidelines specific to the Testflinger Server
Terraform module.

To learn more about the general contribution guidelines for the Testflinger project,
refer to the [Testflinger contribution guide](../../CONTRIBUTING.md).

## Pull Requests

Any change to the terraform modules should be semantically versioned, for automation
to automatically tag your commits, you should consider the following patterns:
- `breaking(terraform-server):` - Creates a major release
- `feat(terraform-server):` - Creates a minor release

By default, any commit without the above patterns will create a patch version bump. 
Refer to [Terraform versioning guide][versioning-guide] to understand more about 
semantic versioning Terraform modules.

## Testflinger Server Terraform Deployment

The following instructions are meant to provide developers a guide on how to
deploy a Testflinger Server by using [Terraform].

### Set up a Juju environment

It is recommended to install the pre-requisites on a VM rather than your host
machine. To do so, first install [Multipass]:

```shell
sudo snap install multipass
```

Then launch a new VM instance (this may take a while):

```shell
multipass launch noble --disk 50G --memory 4G --cpus 2 --name testflinger-juju --mount /path/to/testflinger:/home/ubuntu/testflinger --cloud-init /path/to/testflinger/server/terraform/dev/cloud-init.yaml --timeout 1200
```

Feel free to increase the storage, memory, CPU, or VM name.

> [!NOTE]
> The initialization may time out. That's fine as long as the setup actually completes. 
> You can tell that the setup completed by checking if the Juju models were created.

Check that the models were created:

```shell
multipass exec testflinger-juju -- juju models
```

### Initialize project's terraform

Now that everything has been set up, you can initialize the project's terraform.
The following guide setups a higher-level module to configure the Testflinger
Server Charm deployment.

Change your directory on your host machine to the terraform dev directory:

```shell
cd /path/to/testflinger/server/terraform/dev
```

Then run:

```shell
multipass exec testflinger-juju -- terraform init
```

### Set up variables

Refer to the [README](README.md#api) for the full list of required variables.

The `terraform/dev` directory has sensitive values to be provided before
deployment. Create a `terraform.tfvars` file inside `terraform/dev` with the 
following secrets:

```hcl
jwt_signing_key                = "<your-jwt-signing-key>"
testflinger_secrets_master_key = "<your-secrets-master-key>"
```


> [!NOTE]
> Only `jwt_signing_key` is required. In case `terraform.tfvars` is not provided
> terraform will prompt for the value.

> [!WARNING]
> Never commit `terraform.tfvars` to version control. The file is excluded via
> `.gitignore` for this reason.

### Deploy

In the terraform directory on your host machine, run:

```shell
multipass exec testflinger-juju -- terraform apply -auto-approve
```

Then wait for the deployment to settle and all the statuses to become active.
You can watch the statuses via:

```shell
multipass exec testflinger-juju -- juju status --storage --relations --watch 5s
```

### Connect to your deployment

Look at the IPv4 addresses of your testflinger-juju VM through:

```shell
multipass info testflinger-juju
```

One of these connects to the ingress enabled inside the VM. To figure out which one,
try the following command on each IP address until you get a response:

```shell
curl --connect-to ::<ip-address> http://testflinger.local/v1
```

Once you find the IP address, add the following entry to your host machine's
`/etc/hosts` file:

```text
<ip-address>   testflinger.local
```

After that you should be able to reach the Testflinger frontend on your host
machine's browser through `http://testflinger.local`. You should also be able 
to access the API  through `http://testflinger.local/v1/`.

### Teardown

To take everything down, you can start with terraform:

```shell
multipass exec testflinger-juju -- terraform destroy -auto-approve
```

The above step can take a while and may even get stuck with some applications
in error state. You can watch it through:

```shell
multipass exec testflinger-juju -- juju status --storage --relations --watch 5s
```

To forcefully remove applications stuck in error state:

```shell
multipass exec testflinger-juju -- juju remove-application <application-name> --destroy-storage --force
```

Once everything is down and the juju model has been deleted you can stop the
multipass VM:

```shell
multipass stop testflinger-juju
```

Optionally, delete the VM:

```shell
multipass delete --purge testflinger-juju
```

[Multipass]: https://canonical.com/multipass
[Terraform]: https://developer.hashicorp.com/terraform
[versioning-guide]: https://developer.hashicorp.com/terraform/plugin/best-practices/versioning
