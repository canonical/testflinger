Command Line Interface Configuration
====================================

The Testflinger CLI can be configured on the command line using the parameters described in ``testflinger --help``. However, sometimes it also supports using environment variables, or reading values from a configuration file. This can be helpful for CI/CD environments, or for setting up a config with different default values read from a config file.

The configuration file is read from ``$XDG_CONFIG_HOME/testflinger-cli.conf`` by default, but this can be overridden with the ``--configfile`` parameter.

When a configuration variable is defined in multiple locations, Testflinger resolves the value by applying the following priority order, from highest to lowest:

1. command-line parameter (for example, ``--server <local_server>``)

2. configuration file

3. environment variable

You can show the current values stored in the config file by running ``testflinger config``. If no value is found on the command line, config file, or environment variable, then a safe default value will be used.

To set a configuration value in the config file, you can edit it directly or use ``testflinger config key=value``.

Testflinger Config Variables
----------------------------

The following config values are currently supported:

* server - Testflinger Server URL to use

  * Config file key: ``server``
  * Environment variable: ``TESTFLINGER_SERVER``
  * Default: ``https://testflinger.canonical.com``

* error_threshold - warn the user of possible server/network problems after failing to read from the server after this many consecutive attempts

  * Config file key: ``error_threshold``
  * Environment variable: ``TESTFLINGER_ERROR_THRESHOLD``
  * Default: ``3``

* client_id - Client ID to use for APIs that require authorisation

  * Config file key: ``client_id``
  * Environment variable: ``TESTFLINGER_CLIENT_ID``
  * Default: ``None``

* secret_key - Secret key to use for APIs that require authorisation

  * Config file key: ``server``
  * Environment variable: ``TESTFLINGER_SECRET_KEY``
  * Default: ``None``
