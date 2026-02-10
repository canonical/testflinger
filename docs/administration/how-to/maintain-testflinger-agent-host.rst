Maintain a Testflinger Agent Host
==================================

This guide outlines how to maintain a Testflinger agent host deployed with Juju.
To deploy a Testflinger agent host, please read the :doc:`deploy-testflinger-agent-host` how-to guide.

Update Testflinger Code
-----------------------

To update the Testflinger code used by the agent host, run the
``update-testflinger`` action.

.. code-block:: shell
  
  juju run testflinger-agent-host/0 update-testflinger

.. tip::

    You can optionally specify a branch to pull by providing the ``branch`` parameter.
    e.g. ``juju run testflinger-agent-host/0 update-testflinger --branch=<branch_name>``


Update Agent Configurations
---------------------------

The agent configurations, which are stored in a git repository, are not
pulled regularly. To pull any updates to the configurations, run the
``update-configs`` action.

.. code-block:: shell

  juju run testflinger-agent-host/0 update-configs


The updated configurations will be applied and the agents will be restarted. If
the agents are currently reserved or in a state where they cannot be restarted,
then the updated configurations will not be applied until those agents are
restarted.

Update TF Scripts
------------------

To update the TF scripts used by the agent host, upgrade the charm to the latest version.
This will pull the latest TF scripts and apply them to the agent host.

.. code-block:: shell

  juju refresh testflinger-agent-host


Operating the Agent Host
------------------------

.. note::

  The following instructions assume you SSH into the agent host charm unit.
  You can SSH into the unit using ``juju ssh <charm unit>``.

Using supervisorctl on the agent host to check status
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The agent host is configured to use supervisorctl to manage the agents. 
You can run the following command to see the status of all the
agents configured inside the charm.

.. code-block:: shell

  $ sudo supervisorctl status

Viewing the agent logs
^^^^^^^^^^^^^^^^^^^^^^

To show the logs for a specific agent, run:

.. code-block:: shell

   $ sudo supervisorctl tail <agent name>


You can also use the ``-f`` option to follow the logs.

To show the logs for supervisorctl itself, to see what it's recently started,
stopped, or signalled, you can use:

.. code-block:: shell

   $ sudo supervisorctl maintail

Stopping and restarting agents
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

  The preferred way to handle agent status is via the CLI by following the instructions in the
  :ref:`handling-agent-status` documentation.

You can use the following command to stop a specific agent:

.. code-block:: shell

   $ sudo supervisorctl stop <agent name>

Be aware that other actions on the charm such as ``update-configs`` might later
cause this to restart the agents.

To signal an agent to safely restart when it's no longer running a job, you can
run:

.. code-block:: shell

   $ sudo supervisorctl signal USR1 <agent name>
