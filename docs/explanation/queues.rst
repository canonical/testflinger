Testflinger Queues
==================

The concept of a queue in Testflinger works as a flexible way of routing test
jobs to :doc:`agents <agents>`. It's a bit more like a system of "tags".

When you define a test job in Testflinger, you give it a single `job queue`
in the job definition. When the job is posted to the server, it waits
for an available agent to request jobs from that queue.

Trying to force the scheduling of jobs to :doc:`agents <agents>` would require
the server to maintain state of all :doc:`agents <agents>` at all time, and be
the arbiter of the entire process. Instead, the :doc:`agents <agents>` can
operate autonomously, and maintain their own lifecycle. The
:doc:`agents <agents>` ask for a job when they are available to run one.

Advertised Queues
-----------------

Advertised queues can be configured for an agent to expose certain "well-known"
queues along with descriptions and images that are known to work with them. These
queues can be seen from the CLI by running the `list-queues` command.
It's important to know that this is not an exhaustive list of all queues that can
be used, just the ones that have been intentionally advertised in order to add
a description. Clicking on the "Queues" link at the top of the web UI will show
both the advertised queues as well as the normal ones, and only the advertised ones
will have descriptions.

Because the advertised queues are declared in the agent configuration, there is no
way for the server to know if they are gone forever if an agent goes away. If an
advertised queue is not updated by the agents for more than 7 days, then it will
disappear from the list of queues to make it easier to find the ones that are
still actively being used by agents that are online.