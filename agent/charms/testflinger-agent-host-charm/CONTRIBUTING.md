# Contributing to Testflinger

This document outlines contribution guidelines specific to the Testflinger charm.
To learn more about the general contribution guidelines for the Testflinger project, refer to the [Testflinger contribution guide](../../../CONTRIBUTING.md).

To make contributions to this charm, you'll need a working
[development setup][juju-setup]. If you are setting up a VM manually, you may
want to use [`concierge`][concierge]. To get started run:

```shell
concierge prepare --verbose --juju-channel=3/stable --charmcraft-channel=latest/stable -p machine
```

You can create an environment for development with [`uv`][uv] from within the `agent` directory (you can install it as a [snap][uv-snap]):

```shell
uv sync
source .venv/bin/activate
```

## Testing

This project uses [`tox`][tox] for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
uvx --with tox-uv tox run -e format         # update your code according to linting rules
uvx --with tox-uv tox -e lint               # code style
uvx --with tox-uv tox -e charm-unit         # charm unit tests
uvx --with tox-uv tox -e charm-integration  # charm integration tests
```

## Build the charm

Build the charm with [`charmcraft`][charmcraft-snap]:

```shell
charmcraft pack
```

> [!NOTE]
> Before running the integration tests, you require to build the charm 

[juju-setup]: https://documentation.ubuntu.com/juju/3.6/howto/manage-your-deployment/#set-up-your-deployment-local-testing-and-development
[concierge]: https://snapcraft.io/concierge
[uv]: https://docs.astral.sh/uv
[uv-snap]: https://snapcraft.io/astral-uv
[tox]: https://tox.wiki/en/4.32.0/
[charmcraft-snap]: https://snapcraft.io/charmcraft