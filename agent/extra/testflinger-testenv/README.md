# testflinger-testenv container
[![amd64][docker-amd64-badge]][ghcr-package]
[![arm64][docker-arm64-badge]][ghcr-package]
[![s390x][docker-s390x-badge]][ghcr-package]

This Dockerfile creates a basic test environment for running the test phase of testflinger agents in a Docker container.

It ships the agent-side parts of canonical/certification-lab-ci-tools
(the `scriptlets` on PATH and the `launcher`, `toolbox` and `snapstore`
packages).

## Local build

From this directory:

```shell
docker build --build-arg BASE_IMAGE=ubuntu:22.04 -t testflinger-testenv .
```

The certification-lab-ci-tools version is pinned by the full commit
hash in the `COMMIT_HASH` build argument. To try a different commit locally:

```shell
docker build --build-arg COMMIT_HASH=<full 40-character hash> .
```

## Usage

The testflinger agent host charm runs this image for the test
phase by default (see [`tf-test`][tf-test] in the charm), so the tools are
available to test commands without any extra setup.

The `scriptlets` and the `toolbox`, `launcher` and `snapstore` commands are
available on PATH for the `ubuntu` user:

```shell
docker run --rm -it ghcr.io/canonical/testflinger/testflinger-testenv:jammy
```

The tools live in `/home/ubuntu/tools`, which is also the default `tools`
path relative to the home directory. To override them with another branch,
download `install_tools.sh` to the home directory and run it from there (add
`--skip-device` if the scriptlets should not be copied to the device).

```shell
cd /home/ubuntu
curl -Ls -o install_tools.sh https://raw.githubusercontent.com/canonical/certification-lab-ci-tools/main/install_tools.sh
source install_tools.sh tools --branch <branch> --skip-device
```

Using a different path leaves the bundled scriptlets earlier in `PATH`.

If the device user is not `ubuntu`, export `DEVICE_USER` before using the
scriptlets that connect to the device.

[docker-amd64-badge]: https://img.shields.io/badge/arch-amd64-blue?logo=docker&logoColor=white
[docker-arm64-badge]: https://img.shields.io/badge/arch-arm64-blue?logo=docker&logoColor=white
[docker-s390x-badge]: https://img.shields.io/badge/arch-s390x-blue?logo=docker&logoColor=white
[ghcr-package]: https://github.com/canonical/testflinger/pkgs/container/testflinger%2Ftestflinger-testenv
[tf-test]: ../../charms/testflinger-agent-host-charm/src/tf-cmd-scripts/tf-test