# Contributing to Testflinger Server Charm

This document outlines contribution guidelines specific to the Testflinger Server
Charm. To learn more about the general contribution guidelines for the Testflinger
project, refer to the [Testflinger contribution guide].

To make contributions to this charm, you'll need a working [development setup].
If you are setting up a VM manually, you may want to use [`concierge`]. To get
started run:

```shell
sudo concierge prepare --juju-channel=3/stable --charmcraft-channel=latest/stable -p microk8s
```

You can create an environment for development with [`uv`][uv] from within the
`server/charm`  directory (you can install it as a [snap][uv-snap]):

```shell
uv sync
source .venv/bin/activate
```

## Testing

This project uses [`tox`][tox] for managing test environments. There are some 
pre-configured environments from within the `server/charm` directory that can 
be used for linting and formatting code when you're preparing contributions to
the charm:

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
charmcraft pack
```

[Testflinger contribution guide]: ../CONTRIBUTING.md
[development setup]: https://documentation.ubuntu.com/juju/3.6/howto/manage-your-deployment/#set-up-your-deployment-local-testing-and-development
[uv]: https://github.com/astral-sh/uv
[uv-snap]: https://snapcraft.io/astral-uv
[tox]: https://tox.wiki/en/4.32.0/
[charmcraft]: https://snapcraft.io/charmcraft