# Juju deployment

Local Juju and charm deployment via microk8s and terraform.

## Setup a juju environment

It is recommended to install the pre-requisites on a VM rather than your host machine. To do so, first install multipass:

```bash
sudo snap install multipass
```

Then launch a new VM instance using (this will take a while):

```bash
multipass launch noble --disk 50G --memory 4G --cpus 2 --name testflinger-juju --mount /path/to/testflinger:/home/ubuntu/testflinger --cloud-init /path/to/testflinger/server/terraform/cloud-init.yaml --timeout 1800
```

Feel free to increase the storage, memory, cpu limits or change the VM name.

## Initialize project's terraform

Now that everything has been set up, you can initialize the project's terraform.

In the terraform directory on your host machine, run:

```bash
multipass exec testflinger-juju -- terraform init
```

## Deploy everything

In the terraform directory on your host machine, run:

```bash
multipass exec testflinger-juju -- terraform apply -auto-approve
```

Then wait for the deployment to settle and all the statuses to become active. You can watch the statuses via:

```bash
multipass exec testflinger-juju -- juju status --storage --relations --watch 5s
```

## Connect to your deployment

Look at the IPv4 addresses of your testflinger-juju vm through:

```bash
multipass info testflinger-juju
```

One of these connect to the ingress enabled inside the VM. To figure out which one try the following command on each IP address until you get response:

```bash
curl --connect-to ::<ip-address> http://testflinger.local
```

Once you find the IP address add the following entry to your host machine's `/etc/hosts` file:

```text
<ip-address>   testflinger.local
```

After that you should be able to get to Testflinger frontend on your host machine's browser through the url `http://testflinger.local`. You should also be able to access the API through `http://testflinger.local/v1/`.

## Teardown

To take everything down you can start with terraform:

```bash
multipass exec testflinger-juju -- terraform destroy -auto-approve
```

The above step can take a while and may even get stuck with some applications in error state. You can watch it through:

```bash
multipass exec testflinger-juju -- juju status --storage --relations --watch 5s
```

To forcefully remove applications stuck in error state:

```bash
multipass exec testflinger-juju -- juju remove-application <application-name> --destroy-storage --force
```

Once everything is down and the juju model has been deleted you can stop the multipass VM:

```bash
multipass stop testflinger-juju
```
