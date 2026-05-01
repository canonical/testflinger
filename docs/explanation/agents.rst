.. _explain_agents:

Testflinger Agents
==================

Introduction
--------------

The Testflinger agent is a per-machine service that runs on an agent host
system. The agent is configured with a set of :doc:`queues <queues>` for which
it knows how to run jobs. When it is not running a job, the agent:

   * Asks the server for a job to run from the list of configured :doc:`queues <queues>`
   * Dispatches the device connector to execute each :doc:`phase <../reference/test-phases>` of the job against the device under test (DUT)
   * Reports the results of the job back to the server
   * Uploads artifacts (if any) saved from the job to the server

You can see a list of agents in the Testflinger web interface by clicking on the
"Agents" link in the top navigation bar or by using the ``list-agents``
subcommand of the testflinger CLI. For more information, see :ref:`listing_agents`.

Communication with the Server
------------------------------

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

Agent Host Charms vs Agents
-----------------------------

Administrators of a Testflinger setup must understand the difference between an
Agent and the Agent Host Charms. The Agent Host Charm is managed within a Juju
environment is responsible for running the Agent itself.

Agent Host
----------

The host machine on which the Agent Host Charm and thus the Agent run on. This
is different than the machine which the Agent's device connector will manage.

Agent Host Administration
----------------------------

Agent Host Administration is the concept of managing the running agent charms
on the agent's host machine via Juju. For guidance on how to manage running
agent host charms, see :ref:`howto-manage-agent-host`.

Agent Administration
--------------------

To manage a running agent a Testflinger administrative user can communicate with
the Testflinger server to tell the Agent to go ``offline``, ``online``, or into
``maintenance`` mode. See :ref:`howto-manage-agent`


Agent Operating Modes
---------------------

The agent starts up as ``online`` and will stay ``online`` unless there is a
recurring problem while trying to bring the target machine up. If an agent puts
itself ``offline`` the status comment will look like this:

- Set to offline by agent. Recovery failed during job '<job_id>' execution."

Testflinger administrators can also change the status of running agents via the
command line to either ``offline`` or ``maintenance``. See :ref:`howto-manage-agent`
for more details.

        Agent states follow the job execution phase order:
        - waiting: idle, ready for jobs
        - setup, provision, firmware_update, test, allocate, reserve: running job phases
        - offline, maintenance: offline states
