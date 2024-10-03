# Testflinger Agent Host Charm

## Overview

This charm provides the base system for a host system that will be used for
testflinger device agents. It installs the base dependencies and provides a
target for deploying the "testflinger-agent" along with
"testflinger-device-connector" on top of. Additionally, it copies the scripts
in `src/tf-cmd-scripts/` to the host system. The scripts would be used by the
testflinger-agent to trigger the testflinger-device-connector at each phase.

## Building
To build this charm, first install charmcraft (`sudo snap install --classic
charmcraft`) then run `charmcraft pack`

## Testing
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

## Configuration
Supported options for this charm are:

  - ssh-private-key:
      base64 encoded ssh private keyfile
  - ssh-public-key:
      base64 encoded ssh public keyfile
  - ssh-config:
      config data to write as ~/.ssh/config
  - config-repo:
      Git repo containing device agent config data
  - config-branch:
      Git branch to pull for the config data
  - config-dir:
      Path from the root of the config repo where the directories and configs are located for this agent host

To keep the tf-cmd-scripts files up-to-date, run `juju upgrade-charm
{testflinger-agent-host-application}`.

The config-repo where the Testflinger configs for the agents are stored should
contain a directory tree. The leaf directories should be named the same as the
agent-id configured for the agent in the `testflinger-agent.conf` file, and
this directory should contain the config files for both the agent and the
device connector.  For example, consider a repo containing the configs for
multiple locations and agents. It might have a structure like this:
```
/
- lab1/
  - agent-101/
    - testflinger-agent.conf
    - default.yaml
  - agent-102/
    - testflinger-agent.conf
    - default.yaml
  - ...
- lab2/
  - agent-201/
    - testflinger-agent.conf
    - default.yaml
  - ...
...
```

In order to make the charm consider only the agents under the `lab1` directory,
you should set the config-dir to `lab1`. 

## Actions
The following actions are supported for this charm:

  - update-testflinger:
      This action is used to update the testflinger-agent and install it to a
      location shared by all the agents running on this host.
      This action will trigger all running agents to restart when they are not running a job.
  - update-configs:
      This action pulls the git repo set in the charm config to update the
      agent configs on the agent host.
      This action will run `supervisorctl update` to force start new agents, and stop any agents
      that are no longer configured. This *could* also force restart any agents, if the
      supervisord config for that agent has changed. This should not normally happen. This action
      will also trigger all running agents to restart when they are not running a job in case the
      testflinger config has changed.

## Operational Notes

### Using supervisorctl on the agent host to check status

The agent host is configured to use supervisorctl to manage the agents. From the agent host,
you can run `sudo supervisorctl status` to see the status of all the agents configured on it.

### Viewing the agent logs
To show the logs for a specific agent, run `sudo supervisorctl tail <agent name>`.
You can also use the `-f` option to follow the logs.
To show the logs for supervisorctl itself, to see what it's recently started, stopped, or
signalled, you can use `supervisorctl maintail`.

### Stopping and restarting agents
You can use `sudo supervisorctl stop <agent name>` to stop a specific agent.
Be aware that other actions on the charm such as `update-configs` might later cause this to
restart the agents. In order to mark it offline so that it will no longer process jobs, you may
want to either remove it completely from the configs, or set a disable marker file using
`touch /tmp/TESTFLINGER-DEVICE-OFFLINE-<agent name>` instead.

To signal an agent to safely restart when it's no longer running a job, you can run
`sudo supervisorctl signal USR1 <agent name>`. 

### Updating agent configs

If the agent configs in the config-repo have changed, you can run
`juju run testflinger-agent-host-application/0 update-configs` (use `run-action` for juju < 3.x)
to update the agent configs on the agent host. This will automatically add any new agents,
remove any agents that are no longer configured, and all agents will be sent a signal to restart
when they are not running a job.

### Updating the Testflinger repo

When the code for the agent or device connectors changes, you can run
`juju run testflinger-agent-host-application/0 update-testflinger` to update the Testflinger
repo on the agent host. This will automatically trigger a safe restart on all the agents after
installing the new code.

### Changes to the supervisord configs

Be aware that if you change anything in the supervisord configs under /etc/supervisor/conf.d,
the agents will be **forced** to restart without waiting for running jobs to terminate the next
time you run the `update-configs` action or perform a configuration change in the charm. This
is because it runs `supervisorctl update`. This should not normally happen, but if for some
reason you need to make a change to the charm that causes it to write changes to the supervisord
configs, then you should take precautions to ensure that the agents are not running jobs when
`supervisord update` is run the next time.
