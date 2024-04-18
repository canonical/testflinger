Test phases
==============

The test will go through several phases depending on the configuration of the test job and the configuration Testflinger agent itself. 

Test phases are declarative and run in a sequential order. A test phase will be executed only if both conditions are satisfied:

- The :doc:`agent configuration file <testflinger-agent-conf>` contains the ``<phase>_command`` field and optional commands to run for the test phase.
- The test job contains valid data for this test phase in the ``<phase>_data`` field.

If the ``<phase>_command`` field is not set in the ``testflinger-agent.conf`` file, then that phase will be skipped. Even if the ``<phase>_command`` is configured, if the test job does not contain valid data for the phase, some optional phases that are not mandatory, and will be skipped if the job does not contain data for it, such as the provision, test, allocate, and reserve phases.


Test phase configuration
-------------------------

The following test phases are currently supported.

Setup
~~~~~~~
    
This phase is the first phase to run, and is used to set up the environment for the test. The test job has no input for this phase and it is completely up to the device owner to include commands that may need to run here.

Example agent configuration:

.. code-block:: yaml

    setup_command: echo Nothing needed for setup

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



Firmware update
~~~~~~~~~~~~~~~~~~~

This phase runs after the provision phase, and is used to perform firmware update on the device (if applicable) with the given version in the test job.

To trigger the firmware update phase, provide the following section in the job definition file:

.. code-block:: yaml

  firmware_update_data:
    version: < latest >
    ignore_failure: < false | true >

Variables in ``firmware_update_data``:

* ``version``: The desired firmware level on the device. Currently the only supported value is ``latest``, which upgrades all components in the device with the latest firmware release.
* ``ignore_failure``: If set to false, Testflinger agent will suspend the job if firmware_update phase return a status other than 0, which implies there's a failure during firmware_update phase. If set to true, the job will continue regardless the status of firmware_update phase. The default value is ``false``.

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
* ``timeout``: Reservation time in seconds. The default is one hour (3600), and you can request a reservation for up to 6 hours (21600).
  
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
        - lp:user1
      timeout: 4800

Cleanup 
~~~~~~~~~
This phase runs after the reserve phase, and is used to clean up the device after the test. The test job has no input for this phase and it is completely up to the device owner to include commands that may need to run here.

Example agent configuration:

.. code-block:: yaml

  cleanup_command: echo Consider removing containers or other necessary cleanup steps here


Attachments
------------
In the `provisioning`, `firmware_update` and `test` phases, it is also possible to specify attachments, i.e. local files that are to be copied over to the Testflinger agent host.

* Example job definition:

  .. code-block:: yaml

    job_queue: example-queue
    provision_data:
      attachments:
        - local: "ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz"
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

  The `local` fields specify where the attachments are to be found locally, e.g. on the machine where the CLI is executed. For this particular example, this sort of file tree is expected:

  .. code-block:: bash

    .
    ├── config.json
    ├── images
    │   └── ubuntu-logo.png
    ├── scripts
    │   └── my_test_script.sh
    └── ubuntu-22.04.4-preinstalled-desktop-arm64+raspi.img.xz

  On the agent host, the attachments are placed under the `attachments` folder and distributed in separate sub-folders according to phase. If an `agent` field is provided, the attachments are also moved or renamed accordingly. For the example above, the file tree on the agent host would look like this:

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

Output 
------------

When running Testflinger, your output will be automatically accumulated for each stage (setup, provision, test, cleanup) and sent to the Testflinger server, along with an exit status for each stage. 

If any stage encounters a non-zero exit code, no further stages will be executed, but the outcome will still be sent to the server.

Artifact
---------

If you want to save additional artifacts to the disk along with the output, create a directory for the artifacts from your test command. Any files in the artifacts directory under your test execution directory will automatically be compressed (``tar.gz``) and sent to the Testflinger server.
