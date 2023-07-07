# Deploying with Terraform + Juju + Kubernetes

The `testflinger.tf` plan in this directory can be used for deploying
the Testflinger server into a dev, staging, or production environment.
For development, it is recommended to use Juju with Microk8s.


## Deploying an Environment

For purposes of this example, we will be deploying a **dev**
environment.

This assumes that you have an existing Juju + k8s environment.
Microk8s makes a great environment for development and testing this,
and you can find more information about deploying it and using it with
juju in this howto: https://juju.is/docs/olm/microk8s


1. First, create the model
```
    $ juju add-model testflinger-dev --credential k8s-certification
```

2. The terraform juju provider doesn't currently support specifying storage
requirements. So we need to work around this by manually deploying the
database. You can modify the specified storage requirements to fit your needs.
```
    $ juju deploy -m testflinger-dev --channel=5/edge mongodb-k8s --storage mongodb=10G
```

3. (optional) If you want to use https, you will need to import the
TLS certificate into a k8s secret. To generate and import a self-signed
certificate for *testflinger.local* (as an example), you can use the following
process:
```
    $ openssl genrsa -out ca.key 2048
    $ openssl req -x509 -new -nodes -days 365 -key ca.key -out ca.crt -subj "/CN=testflinger.local"
    $ microk8s kubectl create secret tls my-tls-secret --key ca.key --cert ca.crt
```

4. (optional) Export environment variables to be used in the following steps. If
you choose not to do this, you'll need to either specify them on the command line
for each command, or answer the interactive prompts from terraform.
```
    $ export TF_VAR_environment=dev
    $ export TF_VAR_external_ingress_hostname=testflinger.local
    $ export TF_VAR_tls_secret_name=my-tls-secret
```

5. (First run only) Initialize terraform
```
    $ terraform init
```

6. Since we specify the model name (testflinger-${environment}) in the terraform plan,
and we already created it by hand to deploy mongodb, we need to import that
existing model into the terraform state so that terraform doesn't give
us an error when it tries to create it.
```
    $ terraform import juju_model.testflinger_model testflinger-dev
```

7. Running `terraform plan` will show us what it intends to do without
actually doing it. Look at the output from this and make sure it looks
correct.
```
    $ terraform plan
```

8. Finally, apply the terraform plan. After the initial deployment,
future changes can also be applied using this command without the need
for any of the previous steps. After this settles, everything should
be deployed, and the details will be visible from `juju status`.
```
    $ terraform apply
```
