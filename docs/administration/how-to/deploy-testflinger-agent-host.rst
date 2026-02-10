Deploy a Testflinger Agent Host
================================

This guide outlines how to deploy a Testflinger agent host using Juju. 

Dependencies
------------

Install the following dependencies:

.. code-block:: shell

  $ sudo apt-get install git
  $ sudo snap install juju lxd

LXD
^^^

Make sure LXD is initialized.

.. code-block:: shell

  $ lxd init --auto

.. note::

  Feel free to initialize LXD with a configuration that suits your needs.

Juju
^^^^

Lastly, set up the Juju controller and model that will host the Testflinger
agent host deployment.

.. code-block:: shell

  $ juju bootstrap localhost localhost-controller
  $ juju add-model testflinger-agents localhost

.. note::

  For this example, the Juju model containing the agent hosts is called
  ``testflinger-agents``. Feel free to change the name in your own deployment.

Agent Configurations
--------------------

The Testflinger agent host charm expects the agent configurations to be in a
git repository.

For a simple example, use the following repository layout:

.. code-block:: text

  lab/
  ├─ agent-host-1/
  │  ├─ agent-1/
  |  │  ├─ default.yaml
  |  │  ├─ testflinger-agent.conf
  ├─ agent-host-2/
  │  ├─ agent-2/
  |  │  ├─ default.yaml
  |  │  ├─ testflinger-agent.conf

For more information on the agent configuration syntax, refer to section on
:doc:`the device connector configuration (default.yaml) </reference/device-connector-conf>`
and
:doc:`the agent configuration (testflinger-agent.conf) </reference/testflinger-agent-conf>`

.. _ssh-key:

SSH Key
-------

Create an SSH key pair that the agent host will use to connect to the devices.

.. code-block:: shell

  $ ssh-keygen -t rsa -f id_rsa

Deploy the Agent Host
---------------------

Deploy the Testflinger agent host charm from Charmhub.

.. code-block:: shell

  $ juju deploy testflinger-agent-host \
  --channel=stable \
  --config config-repo='<agent_config_repo>' \
  --config ssh-private-key='<contents_of_id_rsa>' \
  --config ssh-public-key='<contents_of_id_rsa.pub>' \
  --config config-dir='<path_to_agent_configs>'

.. note::

  For additional configuration options,
  refer to the charm's configuration documentation on `Charmhub <https://charmhub.io/testflinger-agent-host/configurations>`_.

Juju Secret
-----------

.. important::

    Authentication is required starting from Testflinger Server v1.5.0.
    Unauthenticated agents will not be able to get jobs from the server.

The Testflinger agent host charm expects a Juju secret containing credentials to authenticate with the Testflinger server.

Create a Juju secret with the necessary credentials and take note of the secret's URI.

.. code-block:: shell

  $ juju add-secret testflinger-credentials client-id='<client_id>' client-secret='<client_secret>'
  secret:<secret URI>

Grant the Testflinger agent host application access to the secret.

.. code-block:: shell

  $ juju grant-access testflinger-agent-host secret:<secret URI>

Finally, add the secret URI to the agent host charm's configuration:

.. code-block:: shell

  $ juju config testflinger-agent-host credentials-secret='<secret URI>'

.. tip::

    For more information on how to create credentials for Testflinger, refer to the
    :doc:`Testflinger Manage Client Permissions </how-to/manage-client-permissions>` documentation.

Networking
----------

Make sure that the agent host is able to access the Testflinger server
defined by the agent configurations. In most cases this means editing your DNS
records. If that is not an option, you will need to add the name resolution to
the agent host's ``/etc/hosts``.

Access the agent host.

.. code-block:: shell

  $ juju ssh agent-host/0

Then add a line to your ``/etc/hosts`` file that may look like the following:

.. code-block:: text

  127.0.0.1  testflinger.local

Additional Setup
----------------

You will need to do some additional setup depending on your provision setup.

MAAS
^^^^

MAAS Account
""""""""""""

Access your MAAS server and create a ``testflinger`` account. When prompted for
the SSH keys to import, add the public :ref:`SSH key <ssh-key>` you generated
earlier.

MAAS Profile
""""""""""""

After you've created your ``testflinger`` MAAS account, find the API key for this
user.

Access the agent host and create a MAAS profile with the ``testflinger`` account's
API key.

.. code-block:: shell

  $ juju ssh agent-host/0
  $ maas login <maas_profile> '<maas_server>' '<maas_api_key>'

No Provision
^^^^^^^^^^^^

If you have agents with the provision type of ``noprovision``, you need to make
sure that your public :ref:`SSH key <ssh-key>` is added to the device so that
the agent is able to communicate with the device.

Terraform
^^^^

If you want to deploy the Testflinger agent host using Terraform, you can refer to the
`Terraform README <https://github.com/canonical/testflinger/blob/main/agent/terraform/README.md>`_ for instructions.

Maintain the Agent Host
-----------------------

To learn how to maintain a deployed agent host, read the
:doc:`maintain-testflinger-agent-host` how-to guide.

