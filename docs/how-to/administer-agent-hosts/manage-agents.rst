.. _howto-manage-agent:

Manage Testflinger Agents
=========================

For disambiguation between Agents from Agent Host Charms see :ref:`explain_agents`
and for guidance on Agent Host Charm administration see: :ref:`howto-manage-agent-host`.

.. _handling-agent-status:

Agent Administration
--------------------

Agents can be set to ``online``, ``offline``, or ``maintenance`` using the CLI.

Set an Agent Offline
~~~~~~~~~~~~~~~~~~~~

.. note::
   The following action require an authenticated ``client_id`` with admin privileges, 
   for more information please refer to :doc:`Create or edit Testflinger admin credentials <../create-admin-user>`,
   if needed, to set an initial admin ``client_id``.

Each agent is designed to process jobs indefinitely by listening for jobs in its specified queues
until any job is available for them. If an agent needs to be set to offline to stop
processing any jobs, its status can be modified from the CLI. This can be useful when there
is some debugging or maintenance needed on the physical machine.
The procedure to take an agent offline could be one of the following:

* Set agent to offline. 

Setting an agent to ``offline`` requires specification of a reason for changing the agent status, provided as a ``--comment``:

.. code-block:: shell

   testflinger-cli admin set agent-status --status offline --agents <agent_name> --comment "<Offline Reason>"


* Set agent to maintenance.

The ``maintenance`` status doesn't current need to define a reason as it uses a predefined comment.

.. code-block:: shell

   testflinger-cli admin set agent-status --status maintenance --agents <agent_name>

In both ``offline`` and ``maintenance`` statuses, the agent will effectively stop
processing jobs immediately if not processing any job, otherwise it will wait until
job completion to change agent status. It is important to note that in any of
the above statuses, the agent will prevent restarting; if a restart signal is
detected it will be deferred until the agent is marked online.

.. tip::

    If you wish to change the status for multiple agents at the same time, you can define a list 
    of the agents you want to change status e.g. ``--agents agent1 agent2 ... agentN``

Set an Agent Online
~~~~~~~~~~~~~~~~~~~

.. note::
   The following action require an authenticated ``client_id`` with admin privileges, 
   for more information please refer to :doc:`Create or edit Testflinger admin credentials <../create-admin-user>` 
   if needed to set an initial admin ``client_id``.

To set an agent to online in order to recover from an unexpected agent failure or after being set 
to offline manually, execute the following command from the CLI:

.. code-block:: shell

   testflinger-cli admin set agent-status --status online --agents <agent_name>

.. tip::

   If you wish to change the status for multiple agents at the same time, you can define a list 
   of the agents you want to change status e.g. ``--agents agent1 agent2 ... agentN``

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

A list of agents communicating with the server can be fetched via the command
line ``list-agents`` command and displayed in several formats. When collecting
the list of agents for display, a variety of filters may also be applied.
Aside from the filter for status, the filters all support use of regular expressions.

The ``list-agents`` subcommand can help to assess the current status of the
Testflinger agents in order to perform maintenance.

Here's an example where the agents selected by the filter are set to ``online``
within a for loop:

.. code-block:: shell

  $ for agent in $(testflinger list-agents --filter-queue "petilil|audino" -1); do testflinger admin set agent-status --agents $agent --status online; done
  Agent audino status is now: waiting
  Agent petilil status is now: waiting

.. tip::

   This can be particularly useful in combination with ``--filter-comment``
   if good comments are made as agents are brought offline.

For more information, see :ref:`listing_agents`.
