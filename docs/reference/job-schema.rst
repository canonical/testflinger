Test job schema
=================

Test jobs can be defined in either YAML or JSON format.

The following table lists the key elements that a job definition file should contain.

.. list-table:: Test job schema
  :header-rows: 1

  * - Field
    - Type 
    - Description
  * - ``job_queue``
    - String
    - Name of the job queue to which you want to submit the job. This field is mandatory.
  * - ``global_timeout``
    - integer
    - | (Optional) Maximum time (in seconds) a job is allowed to run. If the global timeout is reached while a job is still running, Testflinger will close the job immediately. By default, the timeout for each Testflinger agent is 4 hours. 
      | If your test job will presumably take more than 4 hours to complete, you can set a larger number in the ``global_timeout`` field in the test job. However, if a timeout is specified on a device, the value for this parameter will be overridden by the per-device configurations.
  * - ``output_timeout``
    - integer
    - (Optional) Maximum time (in seconds) Testflinger should wait in the ``test`` phase to get output from the job. If the timeout is reached before the test phase has any output, Testflinger will cancel the job. This value should be smaller than, or equal to, the ``global_timeout``.  The default value is 15 minutes. 
  * - ``allocation_timeout``
    - integer
    - (Optional) Maximum time (in seconds) Testflinger should wait in the ``allocate`` phase for multi-device jobs to reach the ``allocated`` state. If the timeout is reached before all devices are allocated, Testflinger will cancel the job. The default timeout to allocate all devices is 2 hours.
  * - ``<phase>_data``
    - dictionary
    - | (Optional) Sections that define the configurations and commands about how the job should be executed in each of the test phases. If any phase encounters a non-zero exit code, no further phases will be executed.
      | Supported test phases include: 
      |   - provision
      |   - firmware_update
      |   - test
      |   - allocate
      |   - reserve 
      | For detailed information about how to define the data to include in each test phase, see :doc:`test-phases`. 

Environment variables
----------------------------

The following environment variables are supported in the test environment on the HOST system (not on the device under test). You can refer to these variables when defining a job:

.. list-table:: Environment variables on the HOST system
  :header-rows: 1

  * - Name
    - Description
  * - ``WPA_BG_SSID``
    -	SSID for BG WiFi access point
  * - ``WPA_BG_PSK``
    - WPA Key for BG WiFi access point
  * - ``WPA_N_SSID``
    - SSID for N WiFi access point
  * - ``WPA_N_PSK``
    - WPA Key for N WiFi access point
  * - ``WPA_AC_SSID``
    - SSID for AC WiFi access point
  * - ``WPA_AC_PSK``
    - WPA Key for AC WiFi access point
  * - ``OPEN_BG_SSID``
    - SSID for OPEN BG WiFi access point
  * - ``OPEN_N_SSID``
    - SSID for OPEN N WiFi access point
  * - ``OPEN_AC_SSID``
    - SSID for OPEN AC WiFi access point
  * - ``DEVICE_IP``
    - IP address of the device under test (used for SSH)


Example job in YAML
----------------------------

The following example YAML file defines a job that provisions the Ubuntu 22.04-jammy system on the device, and print the distribution-specific information on the provisioned device:

.. code-block:: yaml

  job-queue: example-queue
  global-timeout: 28800
  output-timeout: 3600
  provision_data:
    distro: jammy
  test_data:
    test_cmds: |
      ssh -t ubuntu@DEVICE_IP lsb_release -a
