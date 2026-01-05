View agent status
=================

You can view the status of an agent using the agent-status command. This command
displays the current state of an agent, including its status and the queues it
listens to.

.. code-block:: shell

    testflinger-cli agent-status <agent_name>

By default, this command returns a brief status output. You can also request
structured output in JSON or YAML format using the ``--json`` or ``--yaml`` flags:

.. code-block:: shell

    testflinger-cli agent-status <agent_name> --json

.. code-block:: shell

    testflinger-cli agent-status <agent_name> --yaml

The structured output includes additional information such as the number of jobs
waiting and running in each queue the agent listens to.
