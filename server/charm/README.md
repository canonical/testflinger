# Deploying with Juju

To deploy Testflinger server using Juju, there are 3 main charms you'll need:

- [mongodb-k8s]
- [nginx-ingress-integrator]
- [testflinger-k8s]

All of these can currently be pulled from [charmhub], but there are a few extra
steps needed for configuration and integration listed below. You'll also need
a [juju] and k8s environment set up ahead of time. Refer to
[this document][microk8s-setup] to set up a [microk8s] environment.

Additionally, you'll need to enable the following add-ons in microk8s:

- [dns][microk8s-dns]
- [hostpath-storage][microk8s-hostpath-storage]
- [ingress][microk8s-ingress]

## Deploy mongodb-k8s

For a simple test deployment, it is sufficient to just run:

```shell
juju deploy mongodb-k8s --channel=5/edge
```

If you need to add additional storage for the database, you can also add
the option `--storage db=100G`, for example, to allocate 100G from your
storage pool for use by the database.

## Deploy nginx-ingress-integrator

First, deploy nginx-ingress-integrator using:

```shell
juju deploy nginx-ingress-integrator
```

(OPTIONAL) If you want to use https, you'll need to add the TLS secret to a
k8s secret. Refer to [this guide][ingress-tls] for instructions on the process.

Once you've created that secret in k8s, you can update the config for the nginx
charm to use it by running:

```shell
juju config nginx-ingress-integrator tls-secret-name="my-tls-secret"
```

## Deploy testflinger-k8s

To deploy testflinger itself from charmhub, you can use:

```shell
juju deploy testflinger-k8s --channel=edge
juju config testflinger-k8s external-hostname=testflinger.local
```

You can replace `testflinger.local` with any other hostname you wish to use
for the ingress. Just make sure to either configure your DNS or `/etc/hosts`
to use that name for the IP address of the system where you are running
microk8s.

## Integrate (relate) the Charms

To make the charms talk together, you'll need to run:

```shell
juju integrate testflinger-k8s nginx-ingress-integrator
juju integrate testflinger-k8s mongodb-k8s
```

After this, watch `juju status` and/or `juju debug-log` for progress.
Once everything is settled, you should be able to point your web browser
at the hostname you specified above and see the default Testflinger
homepage.

## Integrate (relate) to COS

Testflinger can be integrated to Canonical Observability Stack (COS) to send metrics through a Prometheus endpoint
for later visualization in Grafana. This can be made either via a direct relation between Testflinger and Prometheus/Grafana
charms or using [Grafana Agent][grafana-agent] as an intermediate for example:

```shell
juju integrate testflinger-k8s:metrics-endpoint grafana-agent-k8s:metrics-endpoint
juju integrate testflinger-k8s:grafana-dashboard grafana-agent-k8s:grafana-dashboards-provider
```

[mongodb-k8s]: https://charmhub.io/mongodb-k8s
[nginx-ingress-integrator]: https://charmhub.io/nginx-ingress-integrator
[testflinger-k8s]: https://charmhub.io/testflinger-k8s
[charmhub]: https://charmhub.io/
[juju]: https://juju.is/
[microk8s-setup]: https://juju.is/docs/olm/microk8s
[microk8s]: https://microk8s.io/
[microk8s-dns]: https://microk8s.io/docs/addon-dns
[microk8s-hostpath-storage]: https://microk8s.io/docs/addon-hostpath-storage
[microk8s-ingress]: https://microk8s.io/docs/addon-ingress
[ingress-tls]: https://charmhub.io/nginx-ingress-integrator/docs/secure-an-ingress-with-tls
[grafana-agent]: https://charmhub.io/grafana-agent-k8s