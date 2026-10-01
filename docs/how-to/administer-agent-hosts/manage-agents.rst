.. _howto-manage-agent:

Manage Testflinger Agents
=========================

For disambiguation between Agents from Agent Host Charms see :ref:`explain_agents`
and for guidance on Agent Host Charm administration see:
:ref:`howto-manage-agent-host`.

.. _handling-agent-status:

Agent Administration
--------------------

Agents can be commanded to ``online``, ``offline``, ``maintenance``, or
``restart`` mode using the CLI. Because agents poll the server for instructions,
a mode change takes effect on the agent's next poll after its current job
completes. The server stores the instruction as ``commanded_mode``; once the
agent adopts it, ``mode`` is updated to match.

.. note::
   The following actions require an authenticated ``client_id`` with admin
   privileges. See :doc:`Create or edit Testflinger admin credentials
   <../create-admin-user>` if needed.

Command an Agent Offline
~~~~~~~~~~~~~~~~~~~~~~~~

To stop an agent from processing new jobs:

.. code-block:: shell

   testflinger-cli admin set agent-status --mode offline --agents <agent_name> --comment "<Offline Reason>"

Command an Agent into Maintenance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To place an agent in maintenance mode (no new jobs, no comment required):

.. code-block:: shell

   testflinger-cli admin set agent-status --mode maintenance --agents <agent_name>

In both ``offline`` and ``maintenance`` modes, the agent stops processing new
jobs. If the agent is currently running a job, the mode change is deferred until
the job completes. The ``commanded_mode`` field on the agent record reflects the
pending instruction.

.. tip::

    To change the mode for multiple agents at once, list them all:
    ``--agents agent1 agent2 ... agentN``

Command an Agent Online
~~~~~~~~~~~~~~~~~~~~~~~

To bring an agent back online:

.. code-block:: shell

   testflinger-cli admin set agent-status --mode online --agents <agent_name>

Restart an Agent
~~~~~~~~~~~~~~~~

To instruct an agent to restart:

.. code-block:: shell

   testflinger-cli admin set agent-status --mode restart --agents <agent_name>

Checking for Pending Mode Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a mode change has been commanded but the agent has not yet adopted it
(e.g. it is still finishing a job), ``commanded_mode`` will differ from
``mode``. Use ``--filter-commanded-mode pending`` to find such agents:

.. code-block:: shell

   testflinger list-agents --filter-commanded-mode pending

Agent Selection
---------------

Excluding Agents from Jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~

To schedule a job which will run on a desired queue but excluding some of the
agents on that queue, for example, to exclude agents named ``agent-1`` and
``agent-2`` from a job, add the following to your job definition:

.. code-block:: yaml

  job_queue: my-queue
  exclude_agents:
    - agent-1
    - agent-2
  # ... rest of job definition

For more details on how to use this feature, see :doc:`../../how-to/submit-job`.

Listing Agents
~~~~~~~~~~~~~~

A list of agents communicating with the server can be fetched via the
``list-agents`` command. The ``list-agents`` subcommand can help to assess the
current mode and state of Testflinger agents in order to plan or perform
maintenance.

Here's an example where agents on selected queues are commanded to ``online``
within a for loop:

.. code-block:: shell

  $ for agent in $(testflinger list-agents --filter-queues "petilil|audino" -1); do testflinger admin set agent-status --agents $agent --mode online; done
  Agent audino commanded to mode 'online'.
  Agent petilil commanded to mode 'online'.

.. tip::

   This can be particularly useful in combination with ``--filter-comment``
   if good comments are made as agents are brought offline or into maintenance.

For more information, see :ref:`listing_agents`.
