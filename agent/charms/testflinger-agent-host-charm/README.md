# Overview

This charm provides the base system for a host system that will be used for
testflinger device agents. It installs the base dependencies and provides a
target for deploying the "testflinger-agent" along with
"testflinger-device-connector" on top of. Additionally, it copies the scripts
in `src/tf-cmd-scripts/` to the host system. The scripts would be used by the
testflinger-agent to trigger the testflinger-device-connector at each phase.

# Building
To build this charm, first install charmcraft (`sudo snap install --classic
charmcraft`) then run `charmcraft pack`

# Testing
This charm includes both unit and integration tests. The integration tests
take some time to run and require setting up juju in your test environment
as described [here](https://juju.is/docs/sdk/dev-setup#heading--manual-set-up-juju).

Once you've done that, you can run all the unit and integration tests by
going up 2 directories from here to the `agent` directory, and running:

```
$ tox -e charm
```

For debugging, it can be useful to keep the model that was deployed so that
it can be reused. To do this, you can add a few additional arguments to tox:
```
$ tox -e charm -v -- --model=testmodel --keep-models
```

This will create a model called `testmodel` and keep it after the run is
complete. If you want to reuse it without deploying again, you can
run the same command again with `--no-deploy` at the end.

# Configuration
Supported options for this charm are:

  - ssh-private-key:
      base64 encoded ssh private keyfile
  - ssh-public-key:
      base64 encoded ssh public keyfile

To keep the tf-cmd-scripts files up-to-date, run `juju upgrade-charm
{testflinger-agent-host-application}`.

# Actions
The following actions are supported for this charm:

  - update-testflinger:
      This action is used to update the testflinger-agent and install it to a
      location shared by all the agents running on this host.
  - update-configs:
      This action pulls the git repo set in the charm config to update the
      agent configs on the agent host.
