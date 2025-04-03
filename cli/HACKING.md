# Testflinger CLI

## Build the Snap Package

Testflinger CLI is distributed as a [Snap package][snap].

Install [`snapcraft`][snapcraft]:

```shell
sudo snap install --classic snapcraft
```

Then you can build the Snap package by running `snapcraft`:

```shell
snapcraft pack
```

Then you can install the Snap package locally with the `--dangerous` flag
(replace `testflinger.snap` with the name of the `.snap` file that was
created by the previous command):

```shell
sudo snap install --dangerous testflinger.snap
```

To learn more about `snapcraft`, refer to the
[`snapcraft` documentation][snapcraft-docs].

## Set up your Development Environment

We use [`uv`][uv] to manage our project and dependencies. You should install it
from the [Snap Store][uv-snap] by using the following command:

```shell
sudo snap install --classic astral-uv
```

To create your development environment, run the following:

```shell
uv sync
```

This will create a virtual environment under `.venv`, to activate it, you need
to source the following file:

```shell
source .venv/bin/activate
```

## Manage Dependencies

### Add a dependency

To add a new dependency to `testflinger-cli`, please use `uv`, as it will
automatically add it to both the `pyproject.toml` and `uv.lock` files:

```shell
uv add ...
```

If the dependency is only a development dependency, please add it to the `dev`
dependency group by using the `--dev` flag.

To learn more about the `uv add` command, refer to the
[`uv` documentation][uv-add].

### Remove a dependency

```shell
uv remove ...
```

If the dependency is only a development dependency, please remove it from the
`dev` dependency group by using the `--dev` flag.

To learn more about the `uv remove` command, refer to the
[`uv` documentation][uv-remove].

## Test

To run all our tests, run the `tox` tool. To run it with `uv`, use the following command:

```shell
uvx --with tox-uv tox
```

You can also run `tox` on its own, and it should automatically pull in `tox-uv` as a dependency for running the tests with our `uv` lock file.

```shell
tox
```

[snap]: https://snapcraft.io/testflinger-cli
[snapcraft]: https://snapcraft.io/snapcraft
[snapcraft-docs]: https://snapcraft.io/docs/snapcraft
[uv]: https://docs.astral.sh/uv
[uv-snap]: https://snapcraft.io/astral-uv
[uv-add]: https://docs.astral.sh/uv/reference/cli/#uv-add
[uv-remove]: https://docs.astral.sh/uv/reference/cli/#uv-remove
