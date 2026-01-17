Test phases
==============

The test will go through several phases depending on the configuration of the test job and the configuration Testflinger agent itself. 

Test phases are declarative and run in a sequential order. A test phase will be executed only if both conditions are satisfied:

- The :doc:`agent configuration file <testflinger-agent-conf>` contains the ``<phase>_command`` field and optional commands to run for the test phase.
- The test job contains valid data for this test phase in the ``<phase>_data`` field.

If the ``<phase>_command`` field is not set in the ``testflinger-agent.conf`` file, then that phase will be skipped. Even if the ``<phase>_command`` is configured, if the test job does not contain valid data for the phase, some optional phases that are not mandatory, and will be skipped if the job does not contain data for it, such as the provision, test, allocate, and reserve phases.

The following phases will be skipped if ``<phase>_data`` is not present in the
job definition file or if the ``<phase>_data`` field supports and contains the
``skip`` field set to ``true``:

- :ref:`provision`
- :ref:`firmware_update`
- :ref:`test`
- :ref:`allocate`
- :ref:`reserve`

Test phase configuration
-------------------------

The following test phases are currently supported.

Setup
~~~~~~~
    
This phase is the first phase to run, and is used to set up the environment for the test. The test job has no input for this phase and it is completely up to the device owner to include commands that may need to run here.

Example agent configuration:

.. code-block:: yaml

    setup_command: echo Nothing needed for setup

.. _provision:

Provision
~~~~~~~~~~~~~~~~

This phase runs after the setup phase, and is used to provision the device by installing the image requested in the test job. The image to be used for provisioning is specified in the ``provision_data`` section of the job definition file, in the form of key-value pairs. 

The provision data is normally very small, and provides important hints to the provisioner for the specific platform you want to provision. Because each platform is different, the required keys vary on device type, such as URLs or release channels.

If either ``provision_command`` is missing from the agent configuration, or the ``provision_data`` section is missing from the job, this phase will be skipped.


* Example agent configuration:

  .. code-block:: yaml

    provision_command: testflinger-device-connector muxpi provision -c /path/to/default.yaml testflinger.json
* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      url: http://cdimage.ubuntu.com/ubuntu-core/16/stable/current/image.img.xz    # Data to pass to the provisioning step

The ``kernel`` field can be included in provision_data to select an alternate kernel to install during provisioning. The accepted values for this field correspond to the kernel names that the connected MAAS instance is aware of. (These can be found under the "Deploy" menu's "Kernel" dropdown on the corresponding MAAS instance.)

* Example job definition with ``hwe`` kernel:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      distro: jammy
      kernel: hwe-22.04

.. _firmware_update:

Firmware update
~~~~~~~~~~~~~~~~~~~

This phase runs after the provision phase, and is used to perform firmware update on the device (if applicable) with the given version in the test job.

To trigger the firmware update phase, provide the following section in the job definition file:

.. code-block:: yaml

  firmware_update_data:
    version: < latest >
    ignore_failure: < false | true >

Variables in ``firmware_update_data``:

* ``version``: The desired firmware level on the device. Currently the only shared supported value among different machines is ``latest``, which upgrades all components in the device with the latest firmware release. 
  
  For HPE server machines, user can specify a model-based release version string referring to `HPE Gen10`_, `HPE Gen11`_ and `HPE Gen12`_ firmware repositories. For example, ``2023.09.00.04`` is applicable for HPE Gen10 server machines.

* ``ignore_failure``: If set to false, Testflinger agent will suspend the job if ``firmware_update`` phase return a status other than 0, which implies there's a failure during ``firmware_update`` phase. If set to true, the job will continue regardless the status of ``firmware_update`` phase. The default value is ``false``.

  If either ``firmware_update_command`` is missing from the agent configuration, or the ``firmware_update_data`` section is missing from the job, this phase will be skipped.


* Example agent configuration:

  .. code-block:: yaml

    firmware_update_command: testflinger-device-connector muxpi firmware_update -c /path/to/default.yaml testflinger.json
* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      url: <url>
    firmware_update_data:
      version: latest
      ignore_failure: false

.. _test:

Test
~~~~~~~~~

This phase runs after the provision phase, and is used to run the ``test_cmds`` defined in the ``test_data`` section of the job.        

You can specify the list of commands in either of the two formats:

.. code-block:: yaml
  
  # specify test_cmds as a list:
  test_data:
    test_cmds:
      - a command to run during the test phase
      - another command to run

  #  specify test_cmds as a string:
  test_data:
    test_cmds: |
      a command to run during the test phase
      another command to run


If either ``test_command`` is missing from the agent configuration, or the ``test_data`` section is missing from the job, this phase will be skipped.

* Example agent configuration:
  
  .. code-block:: yaml

    # You may want to consider running test_command under a container
    # in order to ensure a clean environment every time
    test_command: testflinger-device-connector muxpi test -c /path/to/default.yaml testflinger.json
* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      url: <url>
    test_data:
      test_cmds: |
        ssh ubuntu@$DEVICE_IP snap list
        ssh ubuntu@$DEVICE_IP cat /proc/cpuinfo

.. _allocate:

Allocate
~~~~~~~~~~~

This phase runs after the test phase, and is normally only used by multi-device jobs to lock the agent into an allocated state to be externally controlled by another job.

During the allocate phase, the agent gathers the IP information of the device running the job, and pushes the IP to the Testflinger server to include the device IP in the results data of the job_id. Once that data is pushed successfully, the agent will transition the job to an allocated state, so that the parent job can make use of that data. 

If either ``allocate_command`` is missing from the agent configuration, or the the ``allocate_data`` section is missing from the job, this phase will be skipped.


* Example agent configuration:

  .. code-block:: yaml

    allocate_command: testflinger-device-connector muxpi allocate -c /path/to/default.yaml testflinger.json
* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      url: <url>
    allocate_data:
      allocate: true

.. _reserve:

Reserve 
~~~~~~~~~~~

This phase runs after the allocate phase, and is used for reserving a system for manual control by a specified user over SSH. Once the device is provisioned and ready for use, the agent pushes the SSH keys specified to the device for reservation, and then publish the output to the polling log with information on how to reach the device over SSH.

To reserve a device, provide the following section in the job definition file:

.. code-block:: yaml

  reserve_data:
    ssh_keys:
      - <id-provider>:<your-username>
    timeout: <maximum-reservation-duration-seconds>

Variables in ``reserve_data``:

* ``ssh_keys``: The list of public SSH keys to use for reserving the device. Each line includes an identity provider name and your username on the provider's system. Testflinger uses the ``ssh-import-id`` command to import public SSH keys from trusted, online identity. Supported identities are Launchpad (``lp``) and GitHub (``gh``).
* ``timeout``: Reservation time. The default is one hour, and you can request a reservation for up to 6 hours.
  Authenticated clients can request longer :doc:`reservation times <../explanation/extended-reservation>` with prior authorisation.

  The timeout can be specified in two formats:

  - **Seconds** (integer): ``3600`` for 1 hour, ``21600`` for 6 hours
  - **Duration format**: Human-readable format similar to the ``sleep`` command:

    - ``30s`` or ``30sec`` for 30 seconds
    - ``30m`` or ``30min`` for 30 minutes
    - ``5h`` or ``5hour`` for 5 hours
    - ``4d`` or ``4day`` for 4 days
    - Combined formats: ``2h30m`` for 2 hours and 30 minutes, ``1d5h30m`` for 1 day, 5 hours, and 30 minutes
  
If either ``reserve_command`` is missing from the agent configuration, or the the ``reserve_data`` section is missing from the job, this phase will be skipped.


* Example agent configuration:
  
  .. code-block:: yaml

    reserve_command: testflinger-device-connector muxpi reserve -c /path/to/default.yaml testflinger.json  

* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      url: <url>
    reserve_data:
      ssh_keys:
        - "lp:user1"
      timeout: 2h30m  # 2 hours and 30 minutes (equivalent to 9000 seconds)

Note: ``lp:user1`` is a string in the job definition YAML, not a YAML key-value pair, so there should be no space between the colon and the username.

.. _cleanup:

Cleanup 
~~~~~~~~~
This phase runs after the reserve phase, and is used to clean up the device after the test. The test job has no input for this phase and it is completely up to the device owner to include commands that may need to run here.

Example agent configuration:

.. code-block:: yaml

  cleanup_command: echo Consider removing containers or other necessary cleanup steps here


.. _file_attachments:

Attachments
------------
In the ``provisioning``, ``firmware_update`` and ``test`` phases, it is also possible
to specify attachments, i.e. local files that are to be copied over to
the Testflinger agent host.

* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      attachments:
        - local: ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz
      use_attachment: ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz
    test_data:
      attachments:
        - local: "config.json"
          agent: "data/config/config.json"
        - local: "images/ubuntu-logo.png"
        - local: "scripts/my_test_script.sh"
          agent: "script.sh"
      test_cmds: |
        ls -alR
        cat attachments/test/data/config/config.json
        chmod u+x attachments/test/script.sh
        attachments/test/script.sh

  The ``local`` fields specify where the attachments are to be found locally,
  e.g. on the machine where the CLI is executed. Unless otherwise specified,
  relative paths are interpreted in relation to the location of the Testflinger
  job file (which is convenient since the job file and the attachments are
  usually stored together).
  So for this particular example, this sort of file tree is expected:

  .. code-block:: bash

    .
    ├── job.yaml
    ├── config.json
    ├── images
    │   └── ubuntu-logo.png
    ├── scripts
    │   └── my_test_script.sh
    └── ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz

  On the agent host, the attachments are placed under the ``attachments`` folder
  and distributed in separate sub-folders according to phase. If an ``agent``
  field is provided, the attachments are also moved or renamed accordingly.
  For the example above, the file tree on the agent host would look like this:

  .. code-block:: bash

    .
    └── attachments
        ├── provision
        │   └── ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz
        └── test
            ├── data
            │   └── config
            │       └── config.json
            ├── images
            │   └── ubuntu-logo.png
            └── script.sh

The Testflinger CLI also accepts an optional ``--attachments-relative-to`` argument.
When provided, relative paths are interpreted in relation to this reference path,
instead of the default,  i.e. the location of the Testflinger job file.

In the example above, there is no ``url`` field under the ``provision_data`` to specify
where to download the provisioning image from. Instead, there is a ``use_attachment``
field that indicates which attachment should be used as a provisioning image.
The presence of *either* ``url`` or ``use_attachment`` is required.

At the moment, only the :ref:`muxpi` device connector supports provisioning using an attached image.

Output and logging
------------------

When running Testflinger, your output is automatically captured for each test phase and streamed to the Testflinger server in real-time as log fragments.

Log capture and streaming
~~~~~~~~~~~~~~~~~~~~~~~~~~

The agent captures two types of logs for each phase:

**Standard output logs**
  All console output from commands executed during the phase is captured and sent to the server as fragments. This includes:

  - Setup and cleanup command output
  - Device connector provisioning output
  - Test command results
  - Any stderr output from commands

**Serial console logs**
  For device connectors that support serial console access, the serial output is also captured during provisioning and testing. After each phase completes, the agent reads the serial log file and streams it to the server in chunks.

Log fragment structure
~~~~~~~~~~~~~~~~~~~~~~~

Each log fragment includes:

- **fragment_number**: Sequential number starting from 0
- **timestamp**: ISO 8601 timestamp when the fragment was created
- **phase**: The test phase name (setup, provision, test, etc.)
- **log_data**: The actual log content

This structured approach allows you to:

- Query logs by specific test phase
- Retrieve logs from a specific time range
- Get incremental updates using fragment numbers
- Access logs multiple times (they are stored persistently)

Exit status tracking
~~~~~~~~~~~~~~~~~~~~

Along with logs, each test phase records an exit status code:

- **0**: Phase completed successfully
- **Non-zero**: Phase failed

If any stage encounters a non-zero exit code, no further stages will be executed, but the logs and outcome will still be sent to the server.

Retrieving logs
~~~~~~~~~~~~~~~

See :doc:`../how-to/retrieve-logs` for detailed information on how to retrieve and query logs using the CLI or API.

Artifact
---------

You can save additional files from your test run by creating an ``artifacts`` directory in your test commands. 
The Testflinger agent does not create this directory automatically so your test commands must create it and populate it with any files you want to preserve.

After the job completes, the agent will:

1. Check if an ``artifacts`` directory exists in the test execution directory
2. Compress the directory into a ``tar.gz`` archive
3. Upload the archive to the Testflinger server
4. Delete the local ``artifacts`` directory from the agent host

For example, under ``test_cmds``, you can create an artifacts directory and copy files there:

.. code-block:: yaml
    
  job_queue: <queue>
  provision_data:
    <provision-data>
  test_data:
    test_cmds: |
      ssh ubuntu@$DEVICE_IP 'uname -a > /tmp/system_info.txt'
      mkdir -p artifacts
      scp ubuntu@$DEVICE_IP:/tmp/system_info.txt artifacts/

.. note::
  
  From the above example, the first command is executed on the remote device, while the next two commands are executed on the Testflinger Agent.

Artifacts can later be retrieved using the CLI:

.. code-block:: shell

  testflinger-cli artifacts <job_id>