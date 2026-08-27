# Contributing to Testflinger

This document provides the information needed to contribute to Testflinger,
its providers, and its documentation.

## Repository structure

Testflinger is a monorepo with a subproject directory for each of the major
components of Testflinger, such as [`agent`](./agent/), [`cli`](./cli/),
[`common`](./common/), [`device-connectors`](./device-connectors/), and
[`server`](./server/).

## Package and Project Management

Each of the subprojects uses [`uv`][uv] as the package and project manager.
You can install `uv` with snap:

```shell
sudo snap install --classic astral-uv
```

Additionally, this project uses [just] as a task runner, you can install it with:

```shell
uv tool install rust-just
# Alternatively, available as a snap:
# sudo snap install --classic just
```

Then run `just` from anywhere in the repository for usage.

> [!NOTE]
> The project provides `justfile`s in a modular layout, so running `just` from
> different directories will show you the relevant recipes for the sub-project.
> Running `just` from the root of the project will show you a collection of
> top-level recipes, but you can always run `just <component>::<recipe>` to run
> sub-project recipes. Refer to the [just documentation] for more information.

Lastly, it is recommended that you set up the provided pre-commit hooks. Since
the Testflinger project follows a monorepo layout, `prek` is recommended. To
set up `prek`, use the following `just` recipe:

```shell
just pre-commit
```

### Development Environment

[just] provides an alternative way to run formatting, linting and unit tests without needing to be located in each subproject.
All `just` recipes in this repository use `uv` underneath.

If you prefer using `uv` directly, you'll need to set up your virtual environments manually.

Within a subproject, you can set up the virtual environment with the following
command:

```shell
cd <component>
uv sync
```

Then you can activate the virtual environment:

```shell
source .venv/bin/activate
```

To learn more about `uv`, refer to the [`uv` documentation][uv].

### Workshop Development Environment

Along with the other tools, you can use Canonical's `workshop` to develop and
test Testflinger services in a container environment. Consider the following:

#### Workshop Basics

Install workshop:

```shell
# Prerequisite: install/update to the latest stable LXD from the version 6 track:
# If you don't have LXD yet, install version 6:
sudo snap install --channel=6/stable lxd

# If you do have LXD, update to version 6:
sudo snap refresh --channel=6/stable lxd

# Install workshop:
sudo snap install --classic workshop
```

See the [`workshop` documentation][workshop documentation] for more details.

```shell
# See the available workshops for a given project, add `--global` for all known workshops.
workshop list

# Bring up a workshop, e.g. `dev` workshop:
workshop launch dev

# Execute commands in a workshop
workshop exec dev -- echo "hello world"

# Start a terminal session in a workshop
workshop shell dev
```

#### Testflinger dev workshop examples

The following examples demonstrate specific uses of `workshop` and `just` for
typical server development.

Note: the justfile recipes attempt to abstract some of the `workshop` functions
away from the developer for ease of use, but it is still important to understand
certain aspects about the testflinger services, the way that they are run in the
`workshop` container, and how those services can be exposed to the host system.

```shell
# At its simplest: Start the workshop (if necessary), start the testflinger
# server and attempt to connect the service to the host's ports
just workshop serve
```

To allow for multiple `git` worktrees to be used for parallel development of
testflinger features, the workshops must be able to be `connected` and,
importantly, `disconnected` from the host so that the developer may readily
control which workshop is exposed at a given time.

```shell
# Disconnect the workshop container from the local host system.
just workshop disconnect

# Connect the workshop container's internal services to the local host system.
just workshop connect

# Disconnect and then teardown the internal testflinger services.
just workshop teardown

# To see what other commands are available try:
just workshop help

# To execute any just command in the workshop, simply use `workshop exec dev -- just <command>`:
# To follow testflinger server logs:
workshop exec dev -- just server::logs

# To populate the instance with some data:
workshop exec dev -- just server::populate

# For a large data set you could try:
workshop exec dev -- just server::populate \
        --agents 3000 \
        --jobs 500 \
        --queues 4500 \
        --advertised-queues 2

# This command will clean-up the workshop's docker environment. It is not
# implemented in the `server` justfile to avoid it ever being run by mistake
# on the host system.
just workshop docker-prune

```

To allow for testing in an environment where your web browser is able
to connect to a local development IdP (in the development case: dex) we
recommend setting the localhost to match `dex`, `testflinger-server` and also
`testflinger-metrics` via a /etc/hosts entry pointing to localhost.

```shell
# For convenience you can run the following on your hosts file using sudo:
sudo just server::set-up-hosts-file

# Or you can just do it directly:
echo "127.0.0.1 dex testflinger-server testflinger-metrics" | sudo tee -a /etc/hosts
```

### Managing Dependencies

#### Add a Dependency

To add a new dependency to a component, please use `just`, as
it will automatically add it to both the `pyproject.toml` and `uv.lock` files
for the specified component.

```shell
just <component>::add <flags> <package>
```

e.g.

```shell
just server::add 'requests>=2.32.3'
```

Alternatively, you can also use `uv` within each component subproject:

```shell
cd <component>
uv add <package>
```

If the dependency is only a development dependency, please add it to the `dev`
dependency group by using the `--dev` flag.

To learn more about the `uv add` command, refer to the
[`uv` documentation][uv-add].

### Remove a Dependency

To remove a dependency from a subproject, please use `just`, as
it will automatically remove it from both the `pyproject.toml` and `uv.lock`
files:

```shell
just <component>::remove <package>
```

Alternatively, you can also use `uv` within each component subproject:

```shell
cd <component>
uv remove <package>
```

If the dependency is only a development dependency, please remove it from the
`dev` dependency group by using the `--dev` flag.

To learn more about the `uv remove` command, refer to the
[`uv` documentation][uv-remove].

### Update Lock File

If there is a discrepancy between a subproject's `pyproject.toml` and lock file,
you can generate the lock file (`uv.lock`) with:

```shell
just <component>::lock
```

Or alternatively, within each subproject directory:

```shell
cd <component>
uv lock
```

To learn more about the `uv lock` command, refer to the
[`uv` documentation][uv-lock].

## Testing

All of the linters, format checkers, and unit tests can be run automatically.
Before pushing anything, it's a good idea to run tests for the specified component:

```shell
just <component>::check
```

This will run all available checks for the specified component. You can also run them individually:

- `just <component>::lint` (Check code against coding style standards)
- `just <component>::format` (Apply coding style standards to code)
- `just <component>::test` (Run unit tests)

Or run checks for all components at the same time:

```shell
just check
```

Or run linting for all components at the same time:

```shell
just lint
```

If using `uv`, you can run `tox` from the root of the subproject where you made changes.

To run tox with `uv`, use:

```shell
cd <component>
uvx --with tox-uv tox
```

If you have `tox` installed, you can also just run `tox` from the subproject.

In case of any linting or formatting errors, all solvable fixes can be applied with:

```shell
cd <component>
uvx --with tox-uv tox run -e format
```

## Server API Changes

If you modified the server API (endpoints, schemas, or parameters), you must
update and commit the OpenAPI specification file (`server/schemas/openapi.json`) in the
same pull request. The CI check will fail if the spec is out of sync.

To check if the specification is up-to-date, run:

```shell
just server::check-schema
```

Alternatively, within the `server/` directory:

```shell
cd server/
uvx --with tox-uv tox run -e check-schema
```

If the check fails, regenerate the spec:

```shell
just server::schema
```

Or alternatively, within the `server/` directory:

```shell
cd server/
uvx --with tox-uv tox run -e schema
```

Commit the updated spec file with your API changes.

## Signed Commits

- To get your changes accepted, please [sign your commits][signing-commits].
  This practice is enforced by many of the CI pipelines executed in the
  repository (pipelines which use Canonical's [github-runner-operator] operated
  runners).
- If you have just discovered the requirement for signed commits after already
  creating a feature branch with unsigned commits, you can issue
  `git rebase --exec 'git commit --amend --no-edit -n -S' -i main` to sign them.
  To translate this into English:
  - `git rebase --exec`: rebases commits
  - `--exec '...'`: exec command `'...'` after each commit, creating a new commit
  - `git commit --amend --no-edit`: amend a commit without changing its message
    - `-n`: bypass pre-commit and commit-msg hooks
    - `-S`: GPG sign commit
    - `-i`: let the user see and edit the list of commits to rebase
    - `main`: to all the commits until you reach main
- To make commit signing convenient (see this relevant
  [Stack Overflow post][autosign-commits]), do the following:

  ```shell
  git config --global user.signingkey <your-key-id>
  git config --global commit.gpgSign true
  git config --global tag.gpgSign true
  git config --global push.gpgSign if-asked
  ```

## Pull Requests

Pull Requests will be marked as stale after 60 days of inactivity and closed
after another 7 days of inactivity.

## Issues

Issues will be marked as stale after a year of inactivity and closed after
another 7 days of inactivity.

## Documentation

Testflinger documentation is maintained under the [`docs/`](./docs/) subdirectory.
To submit changes to the documentation, please read the [documentation contributing guide](./docs/CONTRIBUTING.md).

[workshop documentation]: https://ubuntu.com/workshop/docs/
[uv]: https://docs.astral.sh/uv
[just]: https://github.com/casey/just
[just documentation]: https://just.systems/man/en/
[uv-add]: https://docs.astral.sh/uv/reference/cli/#uv-add
[uv-remove]: https://docs.astral.sh/uv/reference/cli/#uv-remove
[uv-lock]: https://docs.astral.sh/uv/reference/cli/#uv-lock
[signing-commits]: https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits
[github-runner-operator]: https://github.com/canonical/github-runner-operator
[autosign-commits]: https://stackoverflow.com/a/70484849/504931
