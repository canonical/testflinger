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

### Development Environment

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

To add a new dependency to a subproject, please use `uv`, as
it will automatically add it to both the `pyproject.toml` and `uv.lock` files:

```shell
uv add ...
```

If the dependency is only a development dependency, please add it to the `dev`
dependency group by using the `--dev` flag.

To learn more about the `uv add` command, refer to the
[`uv` documentation][uv-add].

### Remove a Dependency

To remove a dependency from a subproject, please use `uv`, as
it will automatically remove it from both the `pyproject.toml` and `uv.lock`
files:

```shell
uv remove ...
```

If the dependency is only a development dependency, please remove it from the
`dev` dependency group by using the `--dev` flag.

To learn more about the `uv remove` command, refer to the
[`uv` documentation][uv-remove].

### Update Lock File

If there is a discrepancy between a subproject's `pyproject.toml` and lock file,
you can generate the lock file (`uv.lock`) with:

```shell
uv lock
```

To learn more about the `uv lock` command, refer to the
[`uv` documentation][uv-lock].

## Testing

All of the linters, format checkers, and unit tests can be run automatically.
Before pushing anything, it's a good idea to run `tox` from the root of the
subproject where you made changes.

To run tox with `uv`, use:

```shell
uvx --with tox-uv tox
```

If you have `tox` installed, you can also just run `tox` from the subproject.

## Server API Changes

If you modified the server API (endpoints, schemas, or parameters), you must update and commit the OpenAPI specification file (`docs/reference/openapi.json`) in the same pull request. The CI check will fail if the spec is out of sync.

To check if the specification is up-to-date, run:

```shell
uvx --with tox-uv tox -e openapi-check
```

If the check fails, regenerate the spec from the `server/` directory:

```shell
cd server/
FLASK_APP=devel.openapi_app uv run flask spec --output ./openapi.json --quiet
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

## Documentation

Testflinger documentation is maintained under the [`docs/`](./docs/) subdirectory.
To submit changes to the documentation, please read the [documentation contributing guide](./docs/CONTRIBUTING.md).

[uv]: https://docs.astral.sh/uv
[uv-add]: https://docs.astral.sh/uv/reference/cli/#uv-add
[uv-remove]: https://docs.astral.sh/uv/reference/cli/#uv-remove
[uv-lock]: https://docs.astral.sh/uv/reference/cli/#uv-lock
[signing-commits]: https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits
[github-runner-operator]: https://github.com/canonical/github-runner-operator
[autosign-commits]: https://stackoverflow.com/a/70484849/504931
