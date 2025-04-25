# Testflinger CLI

This is the development guide for Testflinger CLI. To see more general
contribution and development recommendations, refer to the
[contribution guide](../CONTRIBUTING.md)

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

[snap]: https://snapcraft.io/testflinger-cli
[snapcraft]: https://snapcraft.io/snapcraft
[snapcraft-docs]: https://snapcraft.io/docs/snapcraft
