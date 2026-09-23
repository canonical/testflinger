# Contributing to Testflinger Agent Host Charm

This document outlines contribution guidelines specific to the Testflinger Agent
Host Charm. To learn more about the general contribution guidelines for the
Testflinger project, refer to the [Testflinger contribution guide].

To make contributions to this charm, you'll need a working [development setup].
If you are setting up a VM manually, you may want to use [`concierge`][concierge]. To get
started run:

```shell
sudo concierge prepare --juju-channel=3/stable --charmcraft-channel=latest/stable -p machine
```

You can create an environment for development with [`uv`][uv] from within the
`agent/charms/testflinger-agent-host-charm` directory (you can install it as a
[snap][uv-snap]):

```shell
uv sync
source .venv/bin/activate
```

## Testing

This project uses [`tox`][tox] for managing test environments. There are some
pre-configured environments from within the `agent/charms/testflinger-agent-host-charm`
directory that can be used for linting and formatting code when you're preparing
contributions to the charm:

```shell
uvx --with tox-uv tox run -e format             # update your code according to linting rules
uvx --with tox-uv tox run -e lint               # code style
uvx --with tox-uv tox run -e unit               # charm unit tests
uvx --with tox-uv tox run -e integration        # charm integration tests
uvx --with tox-uv tox                           # runs 'format', 'lint', and 'unit' environments
```

> [!NOTE]
> Before running the integration tests, you need to build the charm.

## Build the Charm

Build the charm with [`charmcraft`][charmcraft]:

```shell
# On an AMD64 build host:
charmcraft pack --platform amd64 --use-lxd

# On an ARM64 build host:
charmcraft pack --platform arm64 --use-lxd
```

Both platforms retain the Ubuntu 22.04 base. The build host may run a newer
Ubuntu release; Charmcraft uses an isolated build environment. These commands
are native builds, not cross-compilation instructions. Adding ARM64 platform
metadata does not itself publish an ARM64 revision to Charmhub.

### Validate a native build

Use an existing development machine controller with matching architecture.
Do not run the destructive `just setup`/Concierge preparation on an established
lab host merely to run tests; it is intended for disposable development runners.

Select the appropriate controller, then run from this charm directory:

```shell
# On ARM64; use the amd64 artifact on AMD64:
CHARM_PATH="$PWD/testflinger-agent-host_arm64.charm" \
uvx --with tox-uv tox run -e integration -- --juju-dump-logs logs
```

The suite deploys with a constraint matching the test runner's architecture and
checks the guest is Ubuntu 22.04. It exercises workload installation, update
actions, and a transition from one to two agents running under Supervisor.
Set `CHARM_PATH` explicitly when multiple packed artifacts exist.

The initial deployment wait allows 20 minutes for cold image provisioning and
dependency installation, including on SD-backed hosts. This is a test deadline,
not a delay added to every run. If it expires, inspect the captured install logs
before retrying. Package checks use installed source metadata so both regular
and editable local installs are accepted, but installs from another source fail.
Use pytest's `-x` option to stop at the first failure and avoid cascading tests
after an incomplete deployment, for example by appending it after `--` in the
tox command above. The workload is installed from upstream at runtime; packing
the charm does not pin that workload to the feature branch's source revision.

Authentication is bypassed using a mock token in this integration suite. Passing
it is not proof of real server authentication, successful jobs, or USB access.
Before considering ARM64 release-ready, validate the complete install (including
the MAAS snap, Docker, uv, and device-connector dependencies) and real smoke jobs
on an ARM64 host. Keep credentials and tokens out of test reports.

The CI test jobs build and test both native architectures. Charmhub publishing
and architecture-specific release/security scanning require separate validation;
the existing release workflow is not extended by this initial test coverage.
The configuration-repository interface, Supervisor management, and AMD64 base
are unchanged. Direct multi-agent Juju configuration is separate follow-up work.

[Testflinger contribution guide]: ../../../CONTRIBUTING.md
[development setup]: https://documentation.ubuntu.com/juju/3.6/howto/manage-your-deployment/#set-up-your-deployment-local-testing-and-development
[concierge]: https://snapcraft.io/concierge
[uv]: https://github.com/astral-sh/uv
[uv-snap]: https://snapcraft.io/astral-uv
[tox]: https://tox.wiki/en/4.32.0/
[charmcraft]: https://snapcraft.io/charmcraft
