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


You can use the ``job_id`` to further monitor and manager the submitted job.
