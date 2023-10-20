# Overview

This is the charm to deploy the testflinger-agent project.  You can find
the source for testflinger at: https://github.com/canonical/testflinger-agent

The source for testflinger-agent will be pulled directly from git trunk on the
project listed above, for now.

# Building
To build this charm, first install charmcraft (sudo snap install --classic
charmcraft), then run: charmcraft pack

# Configuration
Supported options for this charm are:

  - ssh-priv-key:
      base64 encoded ssh private keyfile
  - ssh-pub-key:
      base64 encoded ssh public keyfile
  - testflinger-agent-configfile:
      base64 encoded string with the config file for spi-agent
  - device-configfile:
      base64 encoded string with the config file for snappy-device-agents
