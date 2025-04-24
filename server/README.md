# Testflinger Server

[![Charmhub][charmhub-badge]][charmhub-site]
[![Documentation status][rtd-badge]][rtd-latest]
[![uv status][uv-badge]][uv-site]

**Testflinger** is a microservice that provides an API to request and enqueue
tests, which can be serviced by any [agent](../agent/README.md) capable of
handling the test.

## Basic Usage

Testflinger is a basic [Flask][flask] application.

You can run it (for example) with `gunicorn`:

```shell
gunicorn --bind: 0.0.0.0:5000 app:app
```

To interact with the server via the CLI, refer to the [Testflinger CLI](../cli/).

To interact with the server via GitHub workflows, refer to the
[Testflinger GitHub actions](../README.md#github-actions)

## Installation

Testflinger is available on all major Linux distributions.

On juju-ready systems, you can deploy it on the command-line with:

```shell
juju deploy testflinger-k8s
```

## Documentation

To learn more about the Testflinger server configuration, deployment, and
maintenance, refer to the following documentation sets:

- [Testflinger charm][charmhub-site]
- [Testflinger documentation on ReadTheDocs][rtd-latest]

## Community and Support

You can report any issues, bugs, or feature requests on the project's
[GitHub repository][github].

## Contribute to Testflinger

Testflinger is open source. Contributions are welcome.

If you're interested, start with the [Server development guide](./HACKING.md)
and the [contribution guide](../CONTRIBUTING.md).

## License and Copyright

Testflinger Server is released under the [GPL-3.0 license](COPYING).

© 2025 Canonical Ltd.

[charmhub-badge]: https://charmhub.io/testflinger-k8s/badge.svg
[charmhub-site]: https://charmhub.io/testflinger-k8s
[rtd-badge]: https://readthedocs.com/projects/canonical-testflinger/badge/?version=latest
[rtd-latest]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[flask]: https://flask.palletsprojects.com/en/stable/
[github]: https://github.com/canonical/testflinger
