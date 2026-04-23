Submit a test job
=================

Once you have a YAML or JSON file with your :doc:`job definition <../reference/job-schema>`,
you can submit the job to the main Testflinger server using the CLI:

.. code-block:: shell

  $ testflinger-cli submit example-job.yaml


If you want to submit the jobs to a Testflinger server other than the default one, see :doc:`change-server`.

If the job is successful submitted, you will see a ``job_id`` returned by Testflinger:

.. code-block:: shell

  Job submitted successfully!
  job_id: 2bac1457-0000-0000-0000-15f23f69fd39


You can use the ``job_id`` to further monitor and manage the submitted job.

You can also store the ``job_id`` in an environment variable, to be able to use it in the following commands:

.. code-block:: shell

   $ JOB_ID="$(testflinger-cli submit -q example-job.yaml)"
   $ testflinger-cli poll "${JOB_ID}"

If you will only need the ``job_id`` for the polling command, you can use:

.. code-block:: shell

   $ testflinger-cli submit --poll example-job.yaml

This will submit and start polling right away.

.. video:: /images/submit-job.mp4
   :alt: Terminal graphic depicting live display of submit --poll with status line.
   :muted:
   :align: center

.. _excluding_agents:

Excluding Select Agents from Running a Job
------------------------------------------

When submitting a job, you can optionally specify a list of agents that should
not run that job using the ``exclude_agents`` field in your job definition.
This is useful in several scenarios:

* Testing workarounds without certain agents
* Avoiding agents known to have hardware or software issues
* Preventing jobs from running on agents undergoing maintenance
* Distributing testing across a subset of available agents

When you exclude agents, the following applies:

* Only agents listed in ``exclude_agents`` are prevented from running the job
* Offline agents are automatically excluded (regardless of the ``exclude_agents`` list)
* At least one available (online) agent must remain after applying exclusions
* If all agents for a queue are excluded, the job submission will fail with an error message

For example, to exclude agents named ``agent-1`` and ``agent-3`` from a job,
consider the following job definition:

.. code-block:: yaml

  job_queue: my-queue
  exclude_agents:
    - agent-1
    - agent-3
  provision_data:
    url: https://example.com/image.img
  test_data:
    test_cmds: |
      echo "This job will not run on agent-1 or agent-3"

Importantly, when you exclude agents, Testflinger will ensure that at least one
agent is available and can still run the job. If all agents in the queue are
excluded, the job submission will fail with an error.
