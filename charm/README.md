# Deploying with Juju

To deploy Testflinger server using Juju, there are 3 main charms you'll need:
 - mongodb-k8s
 - nginx-ingress-integrator
 - testflinger-k8s

All of these can currently be pulled from charmhub, but there are a few extra
steps needed for configuration and integration listed below. You'll also need
a juju and k8s environment set up ahead of time. There are good instructions
for doing this with microk8s here: https://juju.is/docs/olm/microk8s

Additionally, you'll need to enable the following add-ons in microk8s:
 - dns
 - hostpath-storage
 - ingress

## Deploy mongodb-k8s

For a simple test deployment, it is sufficient to just run:
```
    $ juju deploy mongodb-k8s --channel=5/edge
```
If you need to add additional storage for the database, you can also add
the option `--storage db=100G`, for example, to allocate 100G from your
storage pool for use by the database.

## Deploy nginx-ingress-integrator

First, deploy nginx-ingress-integrator using:
```
    $ juju deploy nginx-ingress-integrator
```

(OPTIONAL) If you want to use https, you'll need to add the TLS secret to a
k8s secret.  The process for doing that is described at
https://github.com/canonical/nginx-ingress-integrator-operator/blob/main/docs/how-to/secure-an-ingress-with-tls.md

Once you've created that secret in k8s, you can update the config for the nginx
charm to use it by running:
```
    $ juju config nginx-ingress-integrator tls-secret-name="my-tls-secret"
```

## Deploy testflinger-k8s

To deploy testflinger itself from charmhub, you can use:
```
    $ juju deploy testflinger-k8s --channel=edge
    $ juju config testflinger-k8s external-hostname=testflinger.local
```
You can replace testflinger.local with any other hostname you wish to use
for the ingress. Just make sure to either configure your DNS or /etc/hosts
to use that name for the ip address of the system where you are running
microk8s.

## Integrate (relate) the Charms

To make the charms talk together, you'll need to run:
```
    $ juju integrate testflinger-k8s nginx-ingress-integrator
    $ juju integrate testflinger-k8s mongodb-k8s
```

After this, watch `juju status` and/or `juju debug-log` for progress.
Once everything is settled, you should be able to point your web browser
at the hostname you specified above and see the default testflinger
homepage.