Test job schema
=================

Test jobs can be defined in either YAML or JSON format.

The following table lists the key elements that a job definition file should contain.

.. list-table:: Test job schema
  :header-rows: 1

  * - Field
    - Type 
    - Default
    - Description
  * - ``job_queue``
    - String
    - /
    - Name of the job queue to which you want to submit the job. This field is mandatory.
  * - ``tags``
    - List of strings
    - /
    - | (Optional) List of tags that you want to associate with the job. 
      | Tags can be used to search for jobs with the search API.
  * - ``global_timeout``
    - integer
    - | 14400
      | (4 hours)
    - | (Optional) Maximum time (in seconds) a job is allowed to run. If the global timeout is reached while a job is still running, Testflinger will close the job immediately. 
      | You can set a global timeout larger than the default value, but the per-device configuration might have a more restrict timeout and overwrite the global value.
  * - ``output_timeout``
    - integer
    - | 900
      | (15 minutes)
    - (Optional) Maximum time (in seconds) Testflinger should wait in the ``test`` phase to get output from the job. If the timeout is reached before the test phase has any output, Testflinger will cancel the job. This value should be smaller than, or equal to, the ``global_timeout``. 
  * - ``allocation_timeout``
    - integer
    - | 7200
      | (2 hours)
    - (Optional) Maximum time (in seconds) Testflinger should wait in the ``allocate`` phase for multi-device jobs to reach the ``allocated`` state. If the timeout is reached before all devices are allocated, Testflinger will cancel the job.
  * - ``<phase>_data``
    - dictionary
    - /
    - | (Optional) Sections that define the configurations and commands about how the job should be executed in each of the test phases. If any phase encounters a non-zero exit code, no further phases will be executed.
      | Supported test phases include: 
      |   - provision
      |   - firmware_update
      |   - test
      |   - allocate
      |   - reserve 
      | For detailed information about how to define the data to include in each test phase, see :doc:`test-phases`. 

Example jobs in YAML
----------------------------

The following example YAML file defines a job that provisions the Ubuntu Core 22 system on a Raspberry Pi 4 device. The job retrieves the image from the given URL, provisions the image on the device at IP address stored in the ``$DEVICE_IP`` environment variable, and prints the distribution-specific information on the provisioned device:

.. code-block:: yaml

  job_queue: rpi4b
  global_timeout: 28800
  output_timeout: 3600
  provision_data:
    url: https://cdimage.ubuntu.com/ubuntu-core/22/stable/current/ubuntu-core-22-arm64+raspi.img.xz
  test_data:
    test_cmds: |
      ssh -t ubuntu@$DEVICE_IP lsb_release -a

Data specified in the ``provision_data`` section varies on device types. For example, to provision server images on a MAAS device, the ``distro`` field should be used to indicate the system version. The following YAML file defines a job that provisions the Ubuntu 22.04 LTS (Jammy Jellyfish) server install image on a MAAS device and prints the information about its processors and network interface configurations:

.. code-block:: yaml

  job_queue: maas-x86-node 
  provision_data:   
    distro: jammy 
  test_data:
    test_cmds: |
      ssh ubuntu@$DEVICE_IP cat /proc/cpuinfo
      ssh ubuntu@$DEVICE_IP ifconfig
