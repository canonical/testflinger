Submit a test job
===================

Once you have a YAML or JSON file with your :doc:`job definition <../reference/job-schema>`, you can submit the job to the main Testflinger server using the CLI:

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

Excluding Agents from Running a Job
------------------------------------

You can optionally prevent specific agents from running your job by using the ``exclude_agents`` field in your job definition. This is useful when you want to avoid certain agents due to known issues, maintenance, or other testing requirements.

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

When you exclude agents, Testflinger will validate that at least one available agent can still run the job. If all agents in the queue are excluded, the job submission will fail with an error.
