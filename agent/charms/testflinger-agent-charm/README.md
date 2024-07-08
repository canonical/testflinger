# Overview

This is the charm to deploy Testflinger agents to an agent host.  You can find
the source for testflinger at: https://github.com/canonical/testflinger

The source for testflinger-agent will be pulled directly from git trunk on the
project listed above. This creates a sparse/shallow checkout of testflinger
which only includes the "agent" and "device-connectors" directories since it
doesn't require all of the other parts of the monorepo, and this keeps
the space used for the git checkout to a minimum.

# Building
To build this charm, first install charmcraft (sudo snap install --classic
charmcraft), then run: charmcraft pack

# Configuration
Supported options for this charm are:

  - testflinger-agent-configfile:
      base64 encoded string with the config file for spi-agent
  - device-configfile:
      base64 encoded string with the config file for snappy-device-agents

# Debugging
For local debugging, it might be useful to switch branches and pull updates
in order to test or debug new code. However, because we only clone the
minimum required things from git, you will not see other branches
automatically. In order to change your local clone so that you will see
everythiing, run:

   ```bash 
   $ git remote set-branches origin '*'
   $ git fetch origin
   ```
