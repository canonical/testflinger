# Testflinger Agent Host Charm

[![Charmcraft][charmcraft-badge]][charmcraft-site]
[![uv Status][uv-badge]][uv-site]
[![Ruff status][ruff-badge]][ruff-site]

## Overview

This charm provides the base system for a host system that will be used for
Testflinger device agents. It installs the base dependencies and provides a
target for deploying the `testflinger-agent` along with
`testflinger-device-connector` on top of. Additionally, it copies the scripts
in `src/tf-cmd-scripts/` to the host system. The scripts would be used by the
`testflinger-agent` to trigger the `testflinger-device-connector` at each
phase.

## Basic Usage

On [Juju-ready][juju] systems, you can deploy it on the command-line with:

```shell
juju deploy testflinger-agent-host
```

## Configuration

Supported options for this charm are:

- `ssh-private-key`:
    base64 encoded SSH private keyfile
- `ssh-public-key`:
    base64 encoded SSH public keyfile
- `ssh-config`:
    SSH configuration data to write as `~/.ssh/config`
- `config-repo`:
    Git repository containing device agent configuration data
- `config-branch`:
    Git branch to pull for the configuration data (default: `main`)
- `config-dir`:
    Path from the root of the configuration repository where the
    directories and configurations are located for this agent host
- `testflinger-server`:
    The hostname of the Testflinger server to connect to, this is required
    for authentication (default: `https://testflinger.canonical.com`)
- `credentials-secret`: 
    URI to the Juju Secret that contains the credentials to perform authentication
    against `testflinger-server`

## Actions

The following actions are supported for this charm:

- `update-testflinger`:
    This action is used to update the `testflinger-agent` and install it to a
    location shared by all the agents running on this host.
    This action will trigger all running agents to restart when they are not
    running a job. The following key is optional:
    - `branch`: The name of the branch to pull Testflinger agent code
      from (default if not specified is `main`)
- `update-configs`:
    This action pulls the git repository set in the charm configuration to
    update the agent configurations on the agent host.
    This action will run `supervisorctl update` to force start new agents, and
    stop any agents that are no longer configured. This *could* also force
    restart any agents, if the supervisord configuration for that agent has
    changed. This should not normally happen. This action will also trigger all
    running agents to restart when they are not running a job in case the
    Testflinger configuration has changed.


## Community and Support

You can report any issues, bugs, or feature requests on the project's
[GitHub repository][canonical/testflinger].

## Contribute to the Testflinger Agent Host Charm

The Testflinger Agent Host Charm is open source. Contributions are welcome.

If you're interested, start with the [charm contribution guide](CONTRIBUTING.md).

## License and Copyright

The Testflinger Agent Host Charm is released under the [Apache-2.0 license](LICENSE).

© 2026 Canonical Ltd.

[juju]: https://canonical.com/juju
[charmcraft-badge]: https://charmhub.io/testflinger-agent-host/badge.svg
[charmcraft-site]: https://charmhub.io/testflinger-agent-host
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-site]: https://github.com/astral-sh/uv
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-site]: https://github.com/astral-sh/ruff
[canonical/testflinger]: https://github.com/canonical/testflinger
