# Testflinger Device Connectors

[![Documentation status][rtd-badge]][rtd-latest]
[![codecov][cov-badge]][cov-latest]
[![uv status][uv-badge]][uv-site]
[![Ruff status][ruff-badge]][ruff-site]

**Testflinger Device Connectors** provides a unified way for provisioning,
maintaining, and running tests on devices with different provision types.

## Basic Usage

Given a device's [provision type][provision-types], device connector
[configuration][config-schema], and [job][job-schema], you can provision a
device with the following commands.

> [!NOTE]
> If you are looking for a configuration of an existing machine in our lab, please visit the [Testflinger agent charm configs repository][testflinger-agent-charm-configs].

```shell
testflinger-device-connector $PROVISION_TYPE allocate -c /path/to/default.yaml job.json
```

You can update firmware with:

```shell
testflinger-device-connector $PROVISION_TYPE firmware_update -c /path/to/default.yaml job.json
```

You can run a test on a device with:

```shell
testflinger-device-connector $PROVISION_TYPE runtest -c /path/to/default.yaml job.json
```

You can allocate a device with:

```shell
testflinger-device-connector $PROVISION_TYPE allocate -c /path/to/default.yaml job.json
```

You can reserve a device with:

```shell
testflinger-device-connectors $PROVISION_TYPE reserve -c /path/to/default.yaml job.json
```

To learn more about the different test phases, refer to the
[Test phases][test-phases] documentation.

`testflinger-device-connector` will exit with a value of `46` if something goes
wrong during device recovery. This can be used as an indication that the device
is unusable for some reason, and can't be recovered using automated recovery
mechanisms. The system calling the device connector may want to take further
action, such as alerting someone that it needs manual recovery, or to stop
attempting to run tests on it until it's fixed.

## Installation

Testflinger is available on all major Linux distributions.

You can install `testflinger-device-connectors` with `pip`:

```shell
pip install "testflinger-device-connectors @ git+https://github.com/canonical/testflinger#subdirectory=device-connectors"
```

## Documentation

To learn more about the Testflinger device connectors configuration and usage,
refer to the following documentation:

- [Testflinger documentation on ReadTheDocs][rtd-latest]

## Community and Support

You can report any issues, bugs, or feature requests on the project's
[GitHub repository][github].

## Contribute to Testflinger

Testflinger is open source. Contributions are welcome.

If you're interested, start with the
[Device Connectors development guide](HACKING.md) and the
[contribution guide](../CONTRIBUTING.md).

## License and Copyright

Testflinger Device Connectors is released under the [GPL-3.0 license](COPYING).

© 2025 Canonical Ltd.

[rtd-badge]: https://readthedocs.com/projects/canonical-testflinger/badge/?version=latest
[rtd-latest]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/
[cov-badge]: https://codecov.io/gh/canonical/testflinger/graph/badge.svg?token=G8Y0VF2CEY&component=device
[cov-latest]: https://codecov.io/gh/canonical/testflinger
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[provision-types]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/device-connector-types
[config-schema]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/device-connector-conf
[job-schema]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/job-schema
[test-phases]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/test-phases.html
[github]: https://github.com/canonical/testflinger
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-site]: https://github.com/astral-sh/ruff
[testflinger-agent-charm-configs]: https://github.com/canonical/testflinger-agent-charm-configs
