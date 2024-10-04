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
"Agents" link in the top navigation bar.

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

Safely Restarting or Shutting Down an Agent
-------------------------------------------

When an agent needs to be re-executed due to something like a code update or a
configuration change, it is important to shut it down safely so that it does not
interfere with a job currently running. To do this, you can use one of the
following methods:

1.  create a file called ``/tmp/TESTFLINGER-DEVICE-RESTART-(agent_name)`` (where ``(agent_name)`` is the name of the agent). 
2. Send a SIGUSR1 signal to the agent's process

Both of these methods will cause the agent to exit when it is no longer running
a job. You will need to ensure something like systemd or supervisord is watching
the agent process and restarting it if it exits in order to actually restart the
agent.
