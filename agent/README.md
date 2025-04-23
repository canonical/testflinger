# Testflinger Agent

[![Charmhub][charmhub-badge]][charmhub-site]
[![Documentation status][rtd-badge]][rtd-latest]
[![uv status][uv-badge]][uv-site]

**Testflinger agent** connects to the [Testflinger Server](../server/README.md)
to request and service test submissions.

## Basic Usage

To start an agent process with a given [configuration], simply run:

```shell
testflinger-agent -c /path/to/testflinger-agent.conf
```

## Installation

Testflinger is available on all major Linux distributions.

The [`testflinger-agent-host`][charmhub-site] charm provides a simple way to
deploy multiple agents on a unified host which manages the agents as services
with [Supervisor][supervisord].

On juju-ready systems, you can deploy the agent host on the command-line with:

```shell
juju deploy testflinger-agent-host
```

You can also install `testflinger-agent` as a Python package with `pip`:

```shell
pip install "testflinger-agent @ git+https://github.com/canonical/testflinger#subdirectory=agent"
```

## Documentation

To learn more about the Testflinger agent configuration, deployment, and
maintenance, refer to the following documentation sets:

- [Testflinger agent host charm][charmhub-site]
- [Testflinger documentation on ReadTheDocs][rtd-latest]

## Community and Support

You can report any issues, bugs, or feature requests on the project's
[GitHub repository][github].

## Contribute to Testflinger

Testflinger is open source. Contributions are welcome.

If you're interested, start with the [contribution guide](../CONTRIBUTING.md).

## License and Copyright

© 2025 Canonical Ltd.

[charmhub-badge]: https://charmhub.io/testflinger-agent-host/badge.svg
[charmhub-site]: https://charmhub.io/testflinger-agent-host
[rtd-badge]: https://readthedocs.com/projects/canonical-testflinger/badge/?version=latest
[rtd-latest]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[configuration]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/testflinger-agent-conf.html
[supervisord]: https://supervisord.org/
[github]: https://github.com/canonical/testflinger
