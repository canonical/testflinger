# Testflinger CLI

[![Snapcraft][snapcraft-badge]][snapcraft-site]
[![Documentation status][rtd-badge]][rtd-latest]
[![uv status][uv-badge]][uv-site]

**Testflinger CLI** is the tool for interacting with a Testflinger server. It
can be used to submit jobs, check the status of jobs, and get the job results.

## Basic Usage

A [test job][job-schema] is defined by a YAML or JSON file.

Given a job file, Testflinger submits a new test job with:

```shell
testflinger-cli submit job.yaml
```

After successfully submitting a job, check the status of your job with:

```shell
testflinger-cli status d14d2e31-f239-41b6-9a74-32f538e71cde
```

You can also watch the output of the job as it runs by polling it with:

```shell
testflinger-cli poll d14d2e31-f239-41b6-9a74-32f538e71cde
```

After a job is finished, you can check the results of the test with:

```shell
testflinger-cli results d14d2e31-f239-41b6-9a74-32f538e71cde
```

Finally, you can download the artifact tarball from the test with:

```shell
testflinger-cli artifacts d14d2e31-f239-41b6-9a74-32f538e71cde
```

To see a more detailed tutorial, see the
[Get started with Testflinger CLI][tutorial] tutorial.

## Installation

Testflinger is available on all major Linux distributions.

On snap-ready systems, you can install it on the command-line with:

```shell
sudo snap install testflinger-cli
```

In order for Testflinger to access files/directories in removable media, you
need to connect the `removable-media` interface manually:

```shell
sudo snap connect testflinger-cli:removable-media
```

## Documentation

The Testflinger docs provide guidance and learning material about job
definitions, configuring Testflinger, using authentication (for priority or
restricted queues), and much more:

- [Testflinger documentation on ReadTheDocs][rtd-latest]

## Community and Support

You can report any issues, bugs, or feature requests on the project's
[GitHub repository][github].

## Contribute to Testflinger

Testflinger is open source. Contributions are welcome.

If you're interested, start with the [CLI development guide](HACKING.md) and the
[contribution guide](../CONTRIBUTING.md).

## License and Copyright

Testflinger CLI is released under the [GPL-3.0 license](COPYING).

© 2025 Canonical Ltd.

[snapcraft-badge]: https://snapcraft.io/testflinger-cli/badge.svg
[snapcraft-site]: https://snapcraft.io/testflinger-cli
[rtd-badge]: https://readthedocs.com/projects/canonical-testflinger/badge/?version=latest
[rtd-latest]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[job-schema]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/job-schema.html
[tutorial]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/tutorial/index.html
[github]: https://github.com/canonical/testflinger
