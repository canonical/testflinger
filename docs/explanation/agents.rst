Testflinger Agents
==================

The Testflinger agent is a per-machine service that runs on an agent host
system. The agent is configured with a set of :doc:`queues <queues>` for which
it knows how to run jobs. When it is not running a job, the agent:

   * Asks the server for a job to run from the list of configured :doc:`queues <queues>`
   * Dispatches the device connector to execute each :doc:`phase <../reference/test-phases>` of the job
   * Reports the results of the job back to the server
   * Uploads artifacts (if any) saved from the job to the server

You can see a list of agents in the Testflinger web interface by clicking on the
"Agents" link in the top navigation bar. It is also possible to list the agents
via the ``list-agents`` subcommand of the testflinger CLI, as shown in :ref:`_listing_agents`.

Communication with the Server
-----------------------------

The agent communicates with the server using a REST API. The agent polls the
server for jobs to run at a configurable interval. When a job is found, the agent
downloads the job and any associated artifacts and begins running the job. When
the job is complete, the agent uploads the results and any artifacts to the server.

The server does not push jobs to the agent, and never needs to initiate a connection
to the agent. This makes it easy to run agents behind firewalls or in other
network configurations where the agent cannot be directly reached by the server.
However, it also means that the server has no way of knowing if an agent has gone
away forever if it stops checking in. If this happens, the server will continue to
show the agent in the "Agents" list, but it's important to pay attention to the
timestamp for when the agent was last updated.  This timestamp will continue to
be updated even if the agent is offline as long as the agent is still running and
able to communicate with the server. If an agent has not checked in after 7 days,
it will automatically be removed from the database and will no longer appear in
the "Agents" list.

.. _handling-agent-status:

Agent Administration
--------------------

For more guidance, see :ref: `howto-manage-agent`.

Restarting an Agent
~~~~~~~~~~~~~~~~~~~

When an agent needs to be re-executed due to something like a code update or a
configuration change, it is important to shut it down safely so that it does not
interfere with a job currently running. To do this, you can use the following method:

1. Send a SIGUSR1 signal to the agent's process

This method will cause the agent to exit when it is no longer running
a job. You will need to ensure something like ``systemd`` or ``supervisord`` is watching
the agent process and restarting it if it exits in order to actually restart the
agent.

Set an Agent Offline (admin)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
   The following action require an authenticated ``client_id`` with admin privileges, 
   for more information please refer to :doc:`Create or edit Testflinger admin credentials <../how-to/create-admin-user>` 
   if needed to set an initial admin ``client_id``.

Each agent is designed to process jobs indefinitely by listening for jobs in its specified queues
until any job is available for them. If an agent needs to be set to offline to stop
processing any jobs, its status can be modified from the CLI. This can be useful when there
is some debugging or maintenance needed on the physical machine.
The procedure to offline an agent could be one of the following:

* Set agent to offline. 

Requires a reason for changing the agent status:

.. code-block:: shell

   testflinger-cli admin set agent-status --status offline --agents <agent_name> --comment "<Offline Reason>"


* Set agent to maintenance. 

This status doesn't need to define a reason as it uses a predefined comment.

.. code-block:: shell

   testflinger-cli admin set agent-status --status maintenance --agents <agent_name>

In both statuses, the agent will effectively stop processing jobs immediately if not processing 
any job, otherwise it will wait until job completion to change agent status. It is important to note
that in any of the above statuses, the agent will prevent restarting; if a restart signal is detected
it will be deferred until the agent is marked online. 

.. tip::

    If you wish to change the status for multiple agents at the same time, you can define a list 
    of the agents you want to change status e.g. ``--agents agent1 agent2 ... agentN``

Set an Agent Online (admin)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
   The following action require an authenticated ``client_id`` with admin privileges, 
   for more information please refer to :doc:`Create or edit Testflinger admin credentials <../how-to/create-admin-user>` 
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

.. _excluding_agents:

Excluding Agents from Jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~

When submitting a job, you can optionally specify a list of agents that should not run that job using the ``exclude_agents`` field in your job definition. This is useful in several scenarios:

* Testing workarounds without certain agents
* Avoiding agents known to have hardware or software issues
* Preventing jobs from running on agents undergoing maintenance
* Distributing testing across a subset of available agents

When you exclude agents, the following applies:

* Only agents listed in ``exclude_agents`` are prevented from running the job
* Offline agents are automatically excluded (regardless of the ``exclude_agents`` list)
* At least one available (online) agent must remain after applying exclusions
* If all agents for a queue are excluded, the job submission will fail with an error message

For example, to exclude agents named ``agent-1`` and ``agent-2`` from a job, add the following to your job definition:

.. code-block:: yaml

  job_queue: my-queue
  exclude_agents:
    - agent-1
    - agent-2
  # ... rest of job definition

For more details on how to use this feature, see :doc:`../how-to/submit-job`.

.. _listing_agents:

Listing Agents
~~~~~~~~~~~~~~

A list of agents communicating with the server can be fetched via the command
line and displayed in several formats. When collecting the list of agents for
display, a variety of filters may also be applied. Aside from the filter for
status, the filters all support use of regular expressions.

The ``list-agents`` subcommand can provide output in three different modes:

- Table output (default)

  - Columns specified by comma separated list via ``--fields``

- Status summary (``--summary``)

- Single-column list of agent names (``-1``)

In all cases, filtering can be applied to various fields, e.g:

- Status can be filtered by specifying a list of included and excluded states

  - Available states include: ``online``, ``offline``, and ``maintenance``

    - Fine-grained online states are also available: ``waiting``, ``setup``,
      ``provision``, ``firmware_update``, ``test``, ``allocate``, ``reserve``,
      ``cleanup``

  - States can be _excluded_ if they are preceded by a caret (``^``)

    - e.g.: ``--filter-status online,^waiting``

- Several other agent properties can also be filtered on using regular expression
  matching. All of these take the form of ``--filter-<attribute>`` and will apply
  regular expression matching against the agent's attribute value:

  - ``--filter-name``

  - ``--filter-queues``

  - ``--filter-location``

  - ``--filter-provision-type``

  - ``--filter-comment``

**Table mode (default)**

If neither ``-1`` nor ``--summary`` are specified, the default is to output a
table of agents matching the specified filters. The table fields can be selected
by specifying a comma-separated list of fields via ``--fields``, including any
of: name, status, location, provision_type, comment, job_id, queues. By default
name, status, location, provision_type, and comment are displayed.

.. code-block:: shell

  $ testflinger list-agents
  Name     Status   Location  Provision Type  Comment
  ---------------------------------------------------
  audino   waiting  TXR3-DH1  maas2
  multi-3  waiting            multi
  petilil  waiting  TXR3-DH1  maas2

**Summary mode (--summary)**

.. code-block:: shell

  $ testflinger list-agents --summary
  Online:           2413
    waiting          2328
    provision        28
    test             30
    reserve          27

  Offline:          63
    offline          55
    maintenance      8

Filtering, of course can be used with any output mode, for example:

.. code-block:: shell

  $ testflinger list-agents --summary --filter-status online,^waiting
  Online:           78
    provision        14
    test             12
    reserve          52

  Offline:          0

**Single-column list mode (-1)**

If the purpose of listing the agents is intended to drive shell scripting, it
may be desirable to have a single list of agent names. In single-column list
mode (``-1``) output is suitable for further processing in shell scripts very
much like ``ls -1`` would be used for files.

Here's an example where the agents selected by the filter are set to ``online``
within a for loop:

.. code-block:: shell

  $ for agent in $(testflinger list-agents --filter-queue "petilil|audino" -1); do testflinger admin set agent-status --agents $agent --status online; done
  Agent audino status is now: waiting
  Agent petilil status is now: waiting

.. tip::

   This can be particularly useful in combination with ``--filter-comment``
   if good comments are made as agents are brought offline.
