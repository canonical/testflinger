Reserve a device
================

When you only need an SSH access to the DUT to manually interact with it, you can use a reserve job.

There are two ways to submit a reserve job:
- submit a YAML job definition containing ``reserve_data``
- use the ``reserve`` command with command-line parameters

Using the a job definition file with ``reserve_data``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To reserve a device, provide a job definition which includes ``reserve_data`` such as the following:

.. code-block:: yaml

  job_queue: <queue>
  provision_data:
    <provision-data>
  reserve_data:
    ssh_keys:
      - <id-provider>:<your-username>
    timeout: <maximum-reservation-duration-seconds>

In the ``reserve_data``, you will find:

- ``ssh_keys``: Specifies the list of public SSH keys to use for reserving the device. Each line includes an identity provider name and your username on the provider's system. Supported identities are LaunchPad (``lp``) and GitHub (``gh``).
- ``timeout``: Specifies the reservation time in seconds, default is 1 hour (3600), maximum is 6 hours (21600) without authentication.

If you need more time, see information on authentication and authorisation at :doc:`../how-to/authentication`.

Then submit the job with:

.. code-block:: shell

  $ testflinger-cli submit --poll reserve-job.yaml

Once the device is ready, Testflinger will print out an SSH command that you can use to to access to the device.

When you are finished with the device, you can end your reservation early by cancelling the job. See :doc:`../how-to/cancel-job`.

Using the command line
~~~~~~~~~~~~~~~~~~~~~~

As an alternative for the most basic reserve jobs, you can use the ``reserve`` command to collect the information from the command line and put together a job definition on the fly.

For a ``maas2`` device type, this requires the ``--distro`` parameter:

.. code-block:: shell

  $ testflinger-cli reserve --distro noble --key lp:user --key gh:user --timeout 7200 --queue maas_devices

For most other device types, the ``--image`` parameter corresponds to the ``url:`` key in ``reserve_data``:

.. code-block:: shell

  $ testflinger-cli reserve --image https://image.xz --key lp:user --key gh:user --timeout 7200 --queue other
