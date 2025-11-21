Multi-device jobs
==================

Multi-device jobs allow you to coordinate testing across multiple devices simultaneously. This is useful for scenarios like:

- Network testing between multiple machines
- Client-server application testing
- Distributed system testing
- Multi-node cluster testing

Overview
--------

The ``multi`` device connector orchestrates multiple child jobs, each running on a separate device. The parent job coordinates the provisioning, allocation, and optional reservation of all devices before running coordinated tests.

Workflow
--------

Multi-device jobs follow this phase sequence:

1. **Provision phase**: The multi connector creates and submits child jobs for each device specified in ``provision_data.jobs``. Each child job is submitted to its respective queue and automatically includes:

   - ``allocate_data: {allocate: true}`` - Instructs the child to enter allocated state after provisioning
   - ``parent_job_id`` - Links the child job to the parent for audit trail and credential inheritance

2. **Allocate phase**: The parent job waits for all child jobs to reach the ``allocated`` state. During this phase:

   - Child jobs provision their devices and gather device information (IP addresses)
   - Child jobs post device information to the server
   - Parent job polls child jobs every 10 seconds
   - If ``allocation_timeout`` is reached before all devices are allocated, the job is cancelled

3. **Reserve phase** (optional): If ``reserve_data`` is present, SSH keys are copied to all allocated devices simultaneously, allowing users to connect to all devices during the reservation period.

4. **Test phase** (optional): Coordinated tests can be executed across all devices. Device information is available in ``job_list.json``.

5. **Cleanup phase**: The parent job cancels all child jobs, which triggers cleanup on each device.

Credential inheritance
----------------------

When authenticated users submit multi-device jobs, child jobs automatically inherit authentication permissions from the parent job. This enables:

- **Extended reservation times**: Child jobs can use the parent's ``max_reservation_time`` limits
- **Job priority**: Child jobs inherit the parent's ``max_priority`` settings
- **Restricted queue access**: Child jobs can access queues that require authorization

This inheritance happens automatically through the ``/v1/agent/jobs`` API endpoint used by the multi connector. No additional configuration is required.

Job schema
----------

Basic structure
~~~~~~~~~~~~~~~

.. code-block:: yaml

  job_queue: multi
  allocation_timeout: 7200  # Optional, defaults to 7200 seconds (2 hours)
  provision_data:
    jobs:
      - job_queue: device-queue-1
        provision_data:
          # Device-specific provisioning data
      - job_queue: device-queue-2
        provision_data:
          # Device-specific provisioning data
  reserve_data:  # Optional
    ssh_keys:
      - "gh:your-github-username"
      - "lp:your-launchpad-username"
    timeout: "3600"  # Reservation duration in seconds
  test_data:  # Optional
    test_cmds: |
      # Commands to run across all devices

Required fields
~~~~~~~~~~~~~~~

- ``job_queue``: Must be set to ``multi``
- ``provision_data.jobs``: List of child job definitions, each containing:

  - ``job_queue``: Queue name for the child device
  - ``provision_data``: Device-specific provisioning parameters (varies by device connector type)

Optional fields
~~~~~~~~~~~~~~~

- ``allocation_timeout``: Maximum time (in seconds) to wait for all child jobs to reach allocated state. Default: 7200 (2 hours)
- ``reserve_data``: Configuration for device reservation

  - ``ssh_keys``: List of SSH key identifiers (format: ``provider:username``, e.g., ``gh:username`` or ``lp:username``)
  - ``timeout``: Reservation duration in seconds. Default: 3600 (1 hour). Can also use duration format (e.g., ``2h30m``)

- ``test_data``: Coordinated test commands to run after devices are allocated
- ``test_data.test_username``: SSH username for device connections. Default: ``ubuntu``

Examples
--------

Simple two-device job
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

  job_queue: multi
  provision_data:
    jobs:
      - job_queue: rpi4b
        provision_data:
          url: https://cdimage.ubuntu.com/ubuntu-core/22/stable/current/ubuntu-core-22-arm64+raspi.img.xz
      - job_queue: maas-x86
        provision_data:
          distro: jammy

Multi-device with reservation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

  job_queue: multi
  provision_data:
    jobs:
      - job_queue: device-queue-1
        provision_data:
          distro: jammy
      - job_queue: device-queue-2
        provision_data:
          distro: jammy
      - job_queue: device-queue-3
        provision_data:
          distro: jammy
  reserve_data:
    ssh_keys:
      - "gh:github-username"
      - "lp:launchpad-username"
    timeout: "7200"  # 2 hours
  test_data:
    test_username: ubuntu

Multi-device with coordinated testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

  job_queue: multi
  provision_data:
    jobs:
      - job_queue: server-queue
        provision_data:
          distro: jammy
      - job_queue: client-queue-1
        provision_data:
          distro: jammy
      - job_queue: client-queue-2
        provision_data:
          distro: jammy
  test_data:
    test_cmds: |
      # Parse job_list.json to get device IPs
      SERVER_IP=$(jq -r '.[0].device_info.device_ip' job_list.json)
      CLIENT1_IP=$(jq -r '.[1].device_info.device_ip' job_list.json)
      CLIENT2_IP=$(jq -r '.[2].device_info.device_ip' job_list.json)

      # Start server
      ssh ubuntu@$SERVER_IP "iperf3 -s -D"

      # Run clients
      ssh ubuntu@$CLIENT1_IP "iperf3 -c $SERVER_IP -t 30" &
      ssh ubuntu@$CLIENT2_IP "iperf3 -c $SERVER_IP -t 30" &
      wait

Accessing device information
-----------------------------

After the allocate phase completes, device information is stored in ``job_list.json`` in the job's working directory. The file contains an array of child job objects:

.. code-block:: json

  [
    {
      "job_id": "child-job-uuid-1",
      "device_info": {
        "device_ip": "192.168.1.100"
      }
    },
    {
      "job_id": "child-job-uuid-2",
      "device_info": {
        "device_ip": "192.168.1.101"
      }
    }
  ]

You can parse this file in test commands to access device IPs:

.. code-block:: bash

  # Get first device IP
  DEVICE1_IP=$(jq -r '.[0].device_info.device_ip' job_list.json)

  # Get all device IPs
  ALL_IPS=$(jq -r '.[].device_info.device_ip' job_list.json)

Reservation workflow
--------------------

When ``reserve_data`` is specified, the reserve phase executes after all devices are allocated:

1. The multi connector reads device IPs from ``job_list.json``
2. For each SSH key in ``ssh_keys``:

   - Imports the key using ``ssh-import-id`` (supports GitHub and Launchpad)
   - Copies the key to all device IPs using ``ssh-copy-id``

3. Displays reservation information to the user:

   .. code-block:: text

     *** TESTFLINGER SYSTEMS RESERVED ***
     You can now connect to the following devices:
     ubuntu@192.168.1.100
     ubuntu@192.168.1.101
     ubuntu@192.168.1.102
     Current time:           2025-10-22T10:30:00+00:00
     Reservation expires at: 2025-10-22T11:30:00+00:00
     Reservation will automatically timeout in 3600 seconds
     To end the reservation sooner use: testflinger-cli cancel <job_id>

4. Waits for the reservation timeout duration

**Important notes:**

- The reserve phase uses a separate timeout independent from ``global_timeout``
- Reservation timeout is controlled by ``reserve_data.timeout``
- SSH keys must be accessible via ``ssh-import-id`` (GitHub or Launchpad)
- The ``test_username`` from ``test_data.test_username`` is used for SSH connections (defaults to ``ubuntu``)

Error handling
--------------

Multi-device jobs can fail at various stages:

Allocation failures
~~~~~~~~~~~~~~~~~~~

- **Child job allocation timeout**: If a child job doesn't reach ``allocated`` state within ``allocation_timeout``, the parent job cancels all child jobs and fails
- **Child job fails to allocate**: If a child job enters ``cancelled``, ``complete``, or ``completed`` state during allocation, the parent job cancels remaining child jobs and fails
- **Parent job cancelled**: If the parent job is cancelled during the allocate phase, all child jobs are cancelled

Reservation failures
~~~~~~~~~~~~~~~~~~~~

- **SSH key import failure**: If ``ssh-import-id`` fails after retries, the reservation phase fails
- **SSH key copy failure**: Copy failures to individual devices are logged but don't fail the entire reservation (graceful degradation)
- **Missing job_list.json**: If the allocate phase didn't create device information, the reserve phase fails

Best practices
--------------

1. **Allocation timeout**: Set ``allocation_timeout`` based on the slowest device provisioning time. Default is 2 hours, which should be sufficient for most cases.

2. **Reservation duration**: For authenticated users with extended reservation permissions, you can request longer reservation times (up to the limit configured in your ``max_reservation_time`` permission).

3. **Test username**: If your devices use a non-default username, specify it in ``test_data.test_username``.

4. **Device order**: Child jobs are created in the order specified in ``provision_data.jobs``. This order is preserved in ``job_list.json``, so you can rely on it when parsing device information.

5. **Error recovery**: If a multi-device job fails during allocation, all child jobs are automatically cancelled. You don't need to manually clean up child jobs.

6. **Monitoring**: You can monitor child job status using the Testflinger CLI:

   .. code-block:: bash

     # Get parent job status
     testflinger-cli status <parent-job-id>

     # Get child job IDs from job_list.json (if allocate phase completed)
     testflinger-cli results <parent-job-id>

Authentication requirements
---------------------------

For credential inheritance to work:

1. Submit the parent job with authentication (JWT token via ``testflinger-cli`` login)
2. Ensure your client permissions include the queues used by child jobs
3. Child jobs automatically inherit permissions - no additional authentication needed

If submitting without authentication, multi-device jobs still work but child jobs won't have extended privileges (priority, extended reservations, restricted queue access).

Limitations
-----------

- Maximum number of child jobs: Limited by server capacity and allocation timeout
- Reservation timeout: Limited by ``max_reservation_time`` in your authentication permissions
- All child jobs must successfully allocate for the parent job to proceed
- Child jobs run independently after allocation - there's no built-in synchronization mechanism beyond the test commands you write

See also
--------

- :doc:`../reference/job-schema` - Complete job schema reference
- :doc:`../reference/test-phases` - Detailed information about test phases
- :doc:`../reference/device-connector-types` - Device connector types and provisioning options
- :doc:`../explanation/extended-reservation` - Extended reservation permissions
- :doc:`../explanation/job-priority` - Job priority configuration
- :doc:`../explanation/restricted-queues` - Restricted queue access
