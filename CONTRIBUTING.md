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

Additionally, this project uses [just] as a task runner, you can install with:

```shell
uv tool install rust-just
```

Then run `just` from anywhere in the repository for usage.

### Development Environment

Using [just] is the easiest way to run formatting, linting and unit tests, as it doesn't require you are located in each subproject.
All `just` recipes in this repositories are using `uv` underneath.

If you prefer using uv directly, you'll need to setup your virtual environments manually.

Within a subproject, you can set up the virtual environment with the following
command:

```shell
uv sync
```

Then you can activate the virtual environment:

```shell
source .venv/bin/activate
```

To learn more about `uv`, refer to the [`uv` documentation][uv].

### Managing Dependencies

#### Add a Dependency

To add a new dependency to a component, please use `just`, as
it will automatically add it to both the `pyproject.toml` and `uv.lock` files 
for specified component. 

```shell
just add <component> <flags> <package>
```

e.g

```shell
just add server 'urllib>=2.6.3'
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
just remove <component> <flags> <package>
```

Alternatively, you can also use `uv` within each component subproject:
```shell
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
just lock <component>
```

Or alternatively from each subproject directory:

```shell
uv lock
```

To learn more about the `uv lock` command, refer to the
[`uv` documentation][uv-lock].

## Testing

All of the linters, format checkers, and unit tests can be run automatically.
Before pushing anything, it's a good idea to run tests for the specified component:

```shell
just check <component>
```

This will run all available check for the specified component, you can also run all tests individually:


- `just lint <component>` (Check code against coding style standards)
- `just format <component>` (Apply coding style standards to code)
- `just unit <component>` (Run unit tests)

Or run for linting check for all components at the same time:

```shell
just fast-lint
```

Agent and Server charm code modification requires to run the following recipe in addition to the ones above:

```shell
just charm-unit <component>
```

If using `uv` you can run `tox` from the root of the subproject where you made changes.

To run tox with `uv`, use:

```shell
uvx --with tox-uv tox
```

If you have `tox` installed, you can also just run `tox` from the subproject.

In case of any linting or formatting errors, all solvable fixes can be applied with:

```shell
uvx --with tox-uv tox run -e format
```

## Server API Changes

If you modified the server API (endpoints, schemas, or parameters), you must
update and commit the OpenAPI specification file (`server/schemas/openapi.json`) in the
same pull request. The CI check will fail if the spec is out of sync.

To check if the specification is up-to-date, run:

```shell
just check-schema
```

Alternatively, within the `server/` directory:

```shell
uvx --with tox-uv tox run -e check-schema
```

If the check fails, regenerate the spec 

```shell
just schema
```

Or alternatively, from the `server/` directory:

```shell
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

[uv]: https://docs.astral.sh/uv
[just]: https://github.com/casey/just
[uv-add]: https://docs.astral.sh/uv/reference/cli/#uv-add
[uv-remove]: https://docs.astral.sh/uv/reference/cli/#uv-remove
[uv-lock]: https://docs.astral.sh/uv/reference/cli/#uv-lock
[signing-commits]: https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits
[github-runner-operator]: https://github.com/canonical/github-runner-operator
[autosign-commits]: https://stackoverflow.com/a/70484849/504931
