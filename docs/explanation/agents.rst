Testflinger Agents
==================

The Testflinger agent is a per-machine service that runs on an agent host
system. The agent is configured with a set of :doc:`queues <queues>` for which
it knows how to run jobs. When it is not running a job, the agent:

   * Asks the server for a job to run from the list of configured :doc:`queues <queues>`
   * Dispatches the device connector to execute each :doc:`phase <../reference/test-phases>` of the job
   * Reports the results of the job back to the server
   * Uploads artifacts (if any) saved from the job to the server