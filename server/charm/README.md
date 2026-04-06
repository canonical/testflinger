# Testflinger Server Charm

[![Charmcraft][charmcraft-badge]][charmcraft-site]
[![Test Charm][test-badge]][test-site]
[![uv Status][uv-badge]][uv-site]
[![Ruff status][ruff-badge]][ruff-site]

The **Testflinger Server Charm** operates one or more units of the [Testflinger server](../README.md).
This charm supports deployment on Juju K8s controllers.  

## Basic Usage

On [Juju-ready][juju] systems, you can deploy it on the command-line with:

```shell
juju deploy testflinger-k8s
```

## Relations / Integrations

Currently, supported relations are:

- `mongodb_client`: for interfacing with `mongodb_client`
- `mongodb_keyvault`: for interfacing with `mongodb_client` (for `secrets` encryption database)
- `nginx-route`: for interfacing with `nginx-route`
- `traefik-route`: for interfacing with `traefik_route`

## Contribute to the Testflinger Server Charm

If you're interested, start with the
[charm contribution guide](CONTRIBUTING.md).

[charmcraft-badge]: https://charmhub.io/testflinger-k8s/badge.svg
[charmcraft-site]: https://charmhub.io/testflinger-k8s
[test-badge]: https://github.com/canonical/testflinger/actions/workflows/server-tox.yml/badge.svg
[test-site]: https://github.com/canonical/testflinger/actions/workflows/server-tox.yml
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-site]: https://github.com/astral-sh/ruff
[juju]: https://canonical.com/juju