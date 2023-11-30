Cancel a job
===============

You can cancel a Testflinger job at any point. However, if the job is in the middle of provisioning, it will finish provisioning before cancelling it completely. This prevents accidentally leaving a system in a bad, partially provisioned state. 

To cancel a job, run Testflinger CLI with the ``cancel`` argument and provide the job ID:

.. code-block:: shell
      
      $ testflinger-cli cancel <job_id>


If a job reaches the global timeout or any timeout for a specific operation, such as the output timeout, Testflinger will cancel the job automatically to release resources. In this case, you can resubmit the job or extend the timeout to allow more execution time.
