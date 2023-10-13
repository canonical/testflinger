Testflinger agent configuration options
========================================

By default, configuration of Testflinger agents is loaded from a yaml configuration file called ``testflinger-agent.conf``. You can specify a different file to use for config data using the ``-c`` option.

The following configuration options are supported by the Testflinger Agent:

.. list-table:: Testflinger agents configuration options
    :header-rows: 1

    * - Field
      - Description  
    * - ``agent_id``
      - Unique identifier for this agent
    * - ``polling_interval``
      - Time to sleep between polling for new tests (default: 10s)
    * - ``server_address``
      - Host/IP and port of the Testflinger server
    * - ``execution_basedir``
      - Base directory to use for running jobs (default: ``/tmp/testflinger/run``)
    * - ``logging_basedir``
      - Base directory to use for agent logging (default: ``/tmp/testflinger/logs``)
    * - ``results_basedir``
      - Base directory to use for temporary storage of test results to be transmitted to the server (default: ``/tmp/testflinger/results``)
    * - ``logging_level``
      - Python log level name to use for logging (default: ``INFO``)
    * - ``logging_quiet``
      - Only log to the logfile, and not to the console (default: ``False``)
    * - ``job_queues``
      - List of queues that can be serviced by this device
    * - ``advertised_queues``
      - List of public queue names that should be reported to the server to report to users
    * - ``advertised_images``
      - List of images to associate with a queue name so that they can be referenced by name when using Testflinger reserve
    * - ``global_timeout``
      - Maximum global timeout (in seconds) a job is allowed to specify for this device connector. The job will timeout during the provision or test phase if it takes longer than the requested global_timeout to run. (Default 4 hours)
    * - ``output_timeout``
      - Maximum output timeout (in seconds) a job is allowed to specify for this device connector. The job will timeout if there has been no output in the test phase for longer than the requested output_timeout. (Default 15 min.)
    * - ``setup_command``
      - Command to run for the setup phase
    * - ``provision_command``
      - Command to run for the provision phase
    * - ``allocate_command``
      - Command to run for the allocate phase
    * - ``test_command``
      - Command to run for the testing phase
    * - ``reserve_command``
      - Command to run for the reserve phase - used for optionally reserving a system after provisioning and testing have completed.
    * - ``cleanup_command``
      - Command to run for the cleanup phase
    * - ``provision_type``
      - (optional) type of device connector used. This is sometimes useful when templating the call to the external device-agent command, but is not required

Example configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

  agent_id: rpi-example
  server_address: https://testflinger.canonical.com
  global_timeout: 43200
  output_timeout: 8000
  execution_basedir: /home/ubuntu/testflinger/rpi-example/run
  logging_basedir: /home/ubuntu/testflinger/rpi-example/logs
  results_basedir: /home/ubuntu/testflinger/rpi-example/results
  logging_level: WARNING
  job_queues:
      - rpi4
      - rpi4-001
  setup_command: echo Nothing needed for setup
  provision_command: snappy-device-agent muxpi provision -c /path/to/default.yaml testflinger.json
  allocate_command: snappy-device-agent muxpi allocate -c /path/to/default.yaml testflinger.json
  # You may want to consider running test_command under a container
  # in order to ensure a clean environment every time
  test_command: snappy-device-agent muxpi test -c /path/to/default.yaml testflinger.json
  reserve_command: snappy-device-agent muxpi reserve -c /path/to/default.yaml testflinger.json
  cleanup_command: echo Consider removing containers or other necessary cleanup steps here
  provision_type: muxpi
