Submit a test job with priority
===============================

You can add the :doc:`job_priority <../explanation/job-priority>` field to your
job YAML like this:

.. code-block:: yaml

        job_priority: 100

This field requires an integer value with a default value of 0. The maximum
priority you can set depends on the permissions that you have for the queue
you are submtting to.

In order to use this field, you need to be :doc:`authenticated <./authentication>` with the server.
