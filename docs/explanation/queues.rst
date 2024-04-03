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