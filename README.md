# Testflinger

[![Documentation status][rtd-badge]][rtd-latest]

**Testflinger** is a system for orchestrating the time-sharing of access to a
pool of target machines.

Each Testflinger system consists of:

- A web service (called just Testflinger) that provides an API to request jobs
  by placing them on a queue.
- Per machine agents that wait for jobs to placed on queues they can service and
  then process them.

Jobs can be either fully automated scripts that can attempt to complete within
the allocated time or interactive shell sessions.

The Testflinger system is particular useful for sharing finite machine resources
between different consumers in a predictable fashion.

Typically this has been used for managing a test lab where CI/CD test runs and
also exploratory testing by human operators is desired.

## Documentation

You can find more information and documentation on the
[Testflinger Documentation Page][rtd-latest].

## Contents of this Repository

A full deployment of Testflinger consists of the following components:

- [Testflinger Server][server]: The server hosting the API and Web UI.
- [Testflinger Agent][agent]: Requests and processes jobs from associated
  queues on the server on behalf of a device.
- [Testflinger Device Connectors][device-connectors]: Handles provisioning and
  other device-specific details for each type of device.
- [Testflinger CLI][cli]: The command-line tool for submitting jobs, checking
  status of jobs, and retrieving results.

## GitHub Actions

You can use the following GitHub actions to use Testflinger in your GitHub
workflows:

- [`submit`][submit-action]: Submit a job
- [`poll-multi`][poll-multi-action]: Poll a multi-device agent job

[rtd-badge]: https://readthedocs.com/projects/canonical-testflinger/badge/?version=latest
[rtd-latest]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/
[server]: server/README.rst
[agent]: agent/README.rst
[device-connectors]: device-connectors/README.rst
[cli]: cli/README.rst
[submit-action]: .github/actions/submit/README.md
[poll-multi-action]: .github/actions/poll-multi/README.md
